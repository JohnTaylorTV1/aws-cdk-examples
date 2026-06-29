# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_dynamodb as dynamodb_,
    aws_lambda as lambda_,
    aws_apigateway as apigw_,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_logs as logs,
    aws_cloudtrail as cloudtrail,
    aws_s3 as s3,
    Duration,
    BundlingOptions,
)
from constructs import Construct

TABLE_NAME = "demo_table"


class ApigwHttpApiLambdaDynamodbPythonCdkStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC
        vpc = ec2.Vpc(
            self,
            "Ingress",
            cidr="10.1.0.0/16",
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Private-Subnet", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                )
            ],
        )
        
        # SEC04-BP01: Enable VPC Flow Logs
        vpc_flow_log_group = logs.LogGroup(
            self,
            "VpcFlowLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        vpc.add_flow_log(
            "FlowLog",
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(vpc_flow_log_group),
            traffic_type=ec2.FlowLogTrafficType.ALL
        )
        
        # Create VPC endpoint
        dynamo_db_endpoint = ec2.GatewayVpcEndpoint(
            self,
            "DynamoDBVpce",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            vpc=vpc,
        )

        # This allows to customize the endpoint policy
        dynamo_db_endpoint.add_to_policy(
            iam.PolicyStatement(  # Restrict to listing and describing tables
                principals=[iam.AnyPrincipal()],
                actions=[                "dynamodb:DescribeStream",
                "dynamodb:DescribeTable",
                "dynamodb:Get*",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:CreateTable",
                "dynamodb:Delete*",
                "dynamodb:Update*",
                "dynamodb:PutItem"],
                resources=["*"],
            )
        )

        # SEC04-BP01: Create DynamoDb Table with audit capabilities
        demo_table = dynamodb_.Table(
            self,
            TABLE_NAME,
            partition_key=dynamodb_.Attribute(
                name="id", type=dynamodb_.AttributeType.STRING
            ),
            point_in_time_recovery=True,
            stream=dynamodb_.StreamViewType.NEW_AND_OLD_IMAGES
        )

        # REL05-BP02: Create Lambda function with reserved concurrency
        # REL06-BP07: X-Ray tracing and bundled dependencies
        # Reserved concurrency: 100 concurrent executions
        # Calculation: Expected burst traffic ~500 RPS * avg execution time ~200ms = 100 concurrent
        # This prevents this function from consuming entire account concurrency quota (1000)
        api_hanlder = lambda_.Function(
            self,
            "ApiHandler",
            function_name="apigw_handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            code=lambda_.Code.from_asset(
                "lambda/apigw-handler",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_9.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                )
            ),
            handler="index.handler",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            memory_size=1024,
            timeout=Duration.minutes(5),
            log_retention=logs.RetentionDays.ONE_YEAR,
            tracing=lambda_.Tracing.ACTIVE,
            reserved_concurrent_executions=100
        )

        # grant permission to lambda to write to demo table
        demo_table.grant_write_data(api_hanlder)
        api_hanlder.add_environment("TABLE_NAME", demo_table.table_name)

        # SEC04-BP01: Create log group for API Gateway access logs
        api_log_group = logs.LogGroup(
            self,
            "ApiGatewayAccessLogs",
            retention=logs.RetentionDays.ONE_YEAR,
            removal_policy=RemovalPolicy.DESTROY
        )

        # REL05-BP02: Create API Gateway with explicit throttling limits
        # Throttle settings: 500 burst capacity, 1000 RPS steady-state
        # These limits prevent resource exhaustion while allowing legitimate traffic spikes
        api = apigw_.LambdaRestApi(
            self,
            "Endpoint",
            handler=api_hanlder,
            deploy_options=apigw_.StageOptions(
                access_log_destination=apigw_.LogGroupLogDestination(api_log_group),
                access_log_format=apigw_.AccessLogFormat.clf(),
                logging_level=apigw_.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                tracing_enabled=True,
                throttling_burst_limit=500,
                throttling_rate_limit=1000
            )
        )

        # REL05-BP02: Create API Key for consumer identification
        api_key = apigw_.ApiKey(
            self,
            "ApiKey",
            description="API key for basic tier consumer"
        )

        # REL05-BP02: Create Usage Plan with per-consumer throttling and quota
        # Basic tier: 100 RPS, 200 burst, 10k requests/day
        # Provides granular control over individual API consumers
        usage_plan = apigw_.UsagePlan(
            self,
            "UsagePlan",
            name="BasicUsagePlan",
            description="Basic tier usage plan with per-consumer limits",
            throttle=apigw_.ThrottleSettings(
                rate_limit=100,
                burst_limit=200
            ),
            quota=apigw_.QuotaSettings(
                limit=10000,
                period=apigw_.Period.DAY
            )
        )

        # Associate Usage Plan with API stage
        usage_plan.add_api_stage(
            stage=api.deployment_stage
        )

        # Associate API Key with Usage Plan
        usage_plan.add_api_key(api_key)

        # Output API Key ID for retrieval
        CfnOutput(
            self,
            "ApiKeyId",
            value=api_key.key_id,
            description="API Key ID - retrieve value with: aws apigateway get-api-key --api-key <id> --include-value"
        )

        # SEC04-BP01: Create S3 bucket for CloudTrail logs
        trail_bucket = s3.Bucket(
            self,
            "TrailBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # SEC04-BP01: Create CloudTrail for API activity tracking
        cloudtrail.Trail(
            self,
            "CloudTrail",
            bucket=trail_bucket,
            is_multi_region_trail=True,
            include_global_service_events=True,
            send_to_cloud_watch_logs=True
        )
