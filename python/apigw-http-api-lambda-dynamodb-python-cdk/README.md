
# AWS API Gateway HTTP API to AWS Lambda in VPC to DynamoDB CDK Python Sample!


## Overview

Creates an [AWS Lambda](https://aws.amazon.com/lambda/) function writing to [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) and invoked by [Amazon API Gateway](https://aws.amazon.com/api-gateway/) REST API. 

![architecture](docs/architecture.png)

## AWS Well-Architected Framework Compliance

This stack implements best practices from the AWS Well-Architected Framework:

### SEC04-BP01: Configure service and application logging

**Security Logging Features:**
- **API Gateway Logging**: Access logs and execution logs with CloudWatch integration
- **Lambda Logging**: CloudWatch Logs with 1-year retention policy
- **VPC Flow Logs**: Network traffic monitoring for security analysis
- **CloudTrail**: API activity tracking across all AWS services
- **DynamoDB Audit**: Point-in-Time Recovery and Streams for data change tracking

**Log Retention Policies:**
- **API Gateway Logs**: 1 year
- **Lambda Function Logs**: 1 year
- **VPC Flow Logs**: 1 month
- **CloudTrail Logs**: Stored in S3 with configurable lifecycle

### REL05-BP02: Throttle requests

**API Gateway Throttling:**
- **Burst Limit**: 500 concurrent requests - Handles short traffic spikes while preventing resource exhaustion
- **Rate Limit**: 1000 requests per second - Steady-state throughput limit for predictable backend capacity
- **Protection**: Mitigates retry storms, flooding attacks, and unexpected traffic spikes

**Benefits:**
- Prevents Lambda concurrency exhaustion
- Protects DynamoDB from excessive write traffic
- Returns HTTP 429 (Too Many Requests) when limits exceeded
- Allows workload to operate normally under unexpected volume spikes

### REL06-BP07: Monitor end-to-end tracing of requests through your system

**Distributed Tracing Features:**
- **Lambda X-Ray Tracing**: Active tracing enabled for function execution visibility
- **API Gateway X-Ray Tracing**: Request tracing from API Gateway through downstream services
- **DynamoDB Instrumentation**: Automatic tracing of DynamoDB API calls via X-Ray SDK
- **End-to-End Visibility**: Complete request flow from API Gateway → Lambda → DynamoDB

## Setup

The `cdk.json` file tells the CDK Toolkit how to execute your app.

This project is set up like a standard Python project.  The initialization
process also creates a virtualenv within this project, stored under the `.venv`
directory.  To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package. If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `setup.py` file and rerun the `pip install -r requirements.txt`
command.

## Deploy
At this point you can deploy the stack. 

Using the default profile

```
$ cdk deploy
```

With specific profile

```
$ cdk deploy --profile test
```

## After Deploy

### Testing the API
Navigate to AWS API Gateway console and test the API with below sample data 
```json
{
    "year":"2023", 
    "title":"kkkg",
    "id":"12"
}
```

You should get below response 

```json
{"message": "Successfully inserted data!"}
```

### Accessing Logs

**API Gateway Logs:**
```bash
# View access logs
aws logs tail /aws/apigateway/ApigwHttpApiLambdaDynamodbPythonCdkStack --follow

# Query with CloudWatch Insights
aws logs start-query --log-group-name /aws/apigateway/ApigwHttpApiLambdaDynamodbPythonCdkStack \
  --query-string 'fields @timestamp, @message | sort @timestamp desc | limit 20'
```

**Lambda Logs:**
```bash
# View Lambda execution logs
aws logs tail /aws/lambda/apigw_handler --follow
```

**VPC Flow Logs:**
```bash
# Query VPC Flow Logs
aws logs start-query --log-group-name VpcFlowLogs \
  --query-string 'fields @timestamp, srcAddr, dstAddr, action | filter action = "REJECT"'
```

**CloudTrail:**
```bash
# Query CloudTrail events
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=PutItem
```

### Analyzing X-Ray Traces

**View Service Map:**
```bash
# Open X-Ray console to view service map
aws xray get-service-graph --start-time $(date -u -d '5 minutes ago' +%s) --end-time $(date -u +%s)
```

**Analyze Traces:**
```bash
# Get trace summaries
aws xray get-trace-summaries \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --filter-expression 'service(id(name: "apigw_handler", type: "AWS::Lambda::Function"))'

# Get detailed trace
aws xray batch-get-traces --trace-ids <trace-id>
```

**X-Ray Console:**
Navigate to AWS X-Ray console to:
- View the service map showing API Gateway → Lambda → DynamoDB
- Analyze trace timelines and latencies
- Identify performance bottlenecks
- Debug errors with detailed subsegment information

## Cleanup 
Run below script to delete AWS resources created by this sample stack.
```
cdk destroy
```

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

Enjoy!
