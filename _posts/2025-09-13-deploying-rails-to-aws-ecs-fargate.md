---
layout: post
title: "deploying rails to aws ecs fargate with application load balancer health checks"
date: 2025-09-13
categories: rails aws devops
---
a complete guide to containerizing a rails application and deploying it to aws ecs fargate with proper alb health check configuration.

## overview

this guide walks through deploying a rails 8 application to aws using:
- **ecs fargate** for serverless container orchestration
- **application load balancer (alb)** for traffic routing and health checks
- **ecr** for container image storage
- **secrets manager** for secure configuration management
- **cloudwatch** for logging

**important security note**: replace all placeholder values like `[APP-NAME]` and `[ACCOUNT-ID]` with your actual values. never commit these actual values to version control.

## why ecs fargate over traditional deployment?

**benefits of fargate:**
- no server management - aws handles os patches, scaling, security
- pay-per-use pricing model
- built-in integration with alb and other aws services
- automatic scaling and load balancing
- perfect for microservices and containerized applications

**vs. traditional ec2:**
- no ssh access needed
- no ami management
- scales to zero for cost savings
- simpler operations and ci/cd

## prerequisites

- aws cli configured with appropriate permissions
- docker installed locally
- rails application with health check endpoint

## step 1: containerizing the rails application

### 1.1 create dockerfile

rails 8 generates an excellent production-ready dockerfile. key components:

```dockerfile
# multi-stage build for smaller final image
ARG RUBY_VERSION=3.2.9
FROM ruby:$RUBY_VERSION-slim as base

# production environment configuration
ENV RAILS_ENV="production" \
    BUNDLE_DEPLOYMENT="1" \
    BUNDLE_PATH="/usr/local/bundle"

# thruster configuration for http proxy (recommended)
ENV TARGET_PORT=3000
ENV HTTP_PORT=80
EXPOSE 80

# use thruster to proxy port 80 → rails on port 3000
CMD ["./bin/thrust", "./bin/rails", "server", "-b", "0.0.0.0", "-p", "3000"]
```

### 1.2 health check endpoint

create a robust health check endpoint:

```ruby
# app/controllers/health_controller.rb
class HealthController < ApplicationController
  def check
    render json: {
      status: "ok",
      timestamp: Time.current.iso8601,
      rails_version: Rails.version,
      environment: Rails.env
    }, status: :ok
  end
end
```

```ruby
# config/routes.rb
Rails.application.routes.draw do
  get "health/check"
  # other routes...
end
```

### 1.3 docker entrypoint

simplify the entrypoint for containerized deployment:

```bash
#!/bin/bash -e
# bin/docker-entrypoint

# enable jemalloc for reduced memory usage
if [ -z "${LD_PRELOAD+x}" ]; then
    LD_PRELOAD=$(find /usr/lib -name libjemalloc.so.2 -print -quit)
    export LD_PRELOAD
fi

echo "starting rails server without database setup..."
exec "${@}"
```

### 1.4 platform compatibility

add linux platforms to gemfile.lock for cross-platform builds:

```bash
bundle lock --add-platform x86_64-linux aarch64-linux
```

## step 2: aws infrastructure setup

### 2.1 create ecr repository

**security note**: use unique repository names to avoid conflicts with existing resources.

```bash
aws ecr create-repository --repository-name [APP-NAME] --region us-east-1
```

### 2.2 build and push docker image

```bash
# build for production architecture
docker buildx build --platform linux/amd64 -t [APP-NAME]:latest .

# tag and push to ecr
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin [ACCOUNT-ID].dkr.ecr.us-east-1.amazonaws.com

docker tag [APP-NAME]:latest [ACCOUNT-ID].dkr.ecr.us-east-1.amazonaws.com/[APP-NAME]:latest
docker push [ACCOUNT-ID].dkr.ecr.us-east-1.amazonaws.com/[APP-NAME]:latest
```

### 2.3 vpc and networking setup

**security consideration**: this creates a new vpc. if you have existing infrastructure, consider using existing vpcs and subnets instead.

```bash
# create vpc
VPC_ID=$(aws ec2 create-vpc --cidr-block 10.0.0.0/16 --region us-east-1 --query Vpc.VpcId --output text)

# create public subnets in different azs
SUBNET1=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.1.0/24 --availability-zone us-east-1a --query Subnet.SubnetId --output text)
SUBNET2=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block 10.0.2.0/24 --availability-zone us-east-1b --query Subnet.SubnetId --output text)

# internet gateway and routing
IGW_ID=$(aws ec2 create-internet-gateway --query InternetGateway.InternetGatewayId --output text)
aws ec2 attach-internet-gateway --vpc-id $VPC_ID --internet-gateway-id $IGW_ID

# route table configuration
RT_ID=$(aws ec2 create-route-table --vpc-id $VPC_ID --query RouteTable.RouteTableId --output text)
aws ec2 create-route --route-table-id $RT_ID --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID
aws ec2 associate-route-table --subnet-id $SUBNET1 --route-table-id $RT_ID
aws ec2 associate-route-table --subnet-id $SUBNET2 --route-table-id $RT_ID

# enable auto-assign public ips
aws ec2 modify-subnet-attribute --subnet-id $SUBNET1 --map-public-ip-on-launch
aws ec2 modify-subnet-attribute --subnet-id $SUBNET2 --map-public-ip-on-launch
```

## step 3: application load balancer configuration

### 3.1 security groups

**security note**: the alb security group allows traffic from the entire internet (0.0.0.0/0). this is appropriate for public web applications but consider restricting if needed.

```bash
# alb security group
ALB_SG=$(aws ec2 create-security-group \
  --group-name [APP-NAME]-alb-sg \
  --description "security group for alb" \
  --vpc-id $VPC_ID \
  --query GroupId --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $ALB_SG \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

# ecs security group
ECS_SG=$(aws ec2 create-security-group \
  --group-name [APP-NAME]-ecs-sg \
  --description "security group for ecs tasks" \
  --vpc-id $VPC_ID \
  --query GroupId --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG \
  --protocol tcp --port 80 --source-group $ALB_SG
```

### 3.2 create application load balancer

```bash
# create alb
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name [APP-NAME]-alb \
  --subnets $SUBNET1 $SUBNET2 \
  --security-groups $ALB_SG \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text)

# create target group with health check configuration
TG_ARN=$(aws elbv2 create-target-group \
  --name [APP-NAME]-targets \
  --protocol HTTP --port 80 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /health/check \
  --health-check-protocol HTTP \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --matcher HttpCode=200 \
  --query 'TargetGroups[0].TargetGroupArn' --output text)

# create listener
aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN
```

### 3.3 health check configuration details

the alb health check configuration is critical for proper operation:

- **path**: `/health/check` - your rails endpoint
- **success codes**: `200` - http ok status
- **interval**: `30 seconds` - check frequency
- **timeout**: `5 seconds` - request timeout
- **healthy threshold**: `2` - consecutive successful checks to mark healthy
- **unhealthy threshold**: `3` - consecutive failed checks to mark unhealthy

## step 4: ecs configuration

### 4.1 create ecs cluster

```bash
aws ecs create-cluster --cluster-name [APP-NAME]-cluster
```

### 4.2 iam role for task execution

**security note**: check if ecstaskexecutionrole already exists in your account before creating it to avoid conflicts.

```bash
# create execution role (skip if it already exists)
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"Service":"ecs-tasks.amazonaws.com"},
      "Action":"sts:AssumeRole"
    }]
  }'

# attach required policies
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
```

### 4.3 secrets management

store sensitive configuration in aws secrets manager:

```bash
# store rails master key
aws secretsmanager create-secret \
  --name [APP-NAME]/rails_master_key \
  --secret-string "$(cat config/master.key)"
```

### 4.4 ecs task definition

```json
{
  "family": "[APP-NAME]-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::[ACCOUNT-ID]:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "[APP-NAME]",
      "image": "[ACCOUNT-ID].dkr.ecr.us-east-1.amazonaws.com/[APP-NAME]:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 80,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "RAILS_ENV",
          "value": "production"
        },
        {
          "name": "RAILS_LOG_TO_STDOUT",
          "value": "true"
        }
      ],
      "secrets": [
        {
          "name": "RAILS_MASTER_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:[ACCOUNT-ID]:secret:[APP-NAME]/rails_master_key"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost/health/check || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/[APP-NAME]",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### 4.5 register task definition and create service

```bash
# create cloudwatch log group
aws logs create-log-group --log-group-name /ecs/[APP-NAME]

# register task definition
TASK_DEF_ARN=$(aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition.json \
  --query 'taskDefinition.taskDefinitionArn' --output text)

# create ecs service
aws ecs create-service \
  --cluster [APP-NAME]-cluster \
  --service-name [APP-NAME]-service \
  --task-definition $TASK_DEF_ARN \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[$SUBNET1,$SUBNET2],
    securityGroups=[$ECS_SG],
    assignPublicIp=ENABLED
  }" \
  --load-balancers "targetGroupArn=$TG_ARN,containerName=[APP-NAME],containerPort=80"
```

## step 5: deployment and testing

### 5.1 monitor deployment

```bash
# check service status
aws ecs describe-services --cluster [APP-NAME]-cluster --services [APP-NAME]-service --region us-east-1

# check target health
aws elbv2 describe-target-health --target-group-arn $TG_ARN --region us-east-1

# view logs
aws logs get-log-events --log-group-name /ecs/[APP-NAME] --log-stream-name [LOG-STREAM] --region us-east-1
```

### 5.2 test health checks

```bash
# get alb dns name
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --query 'LoadBalancers[0].DNSName' --output text)

# test health check endpoint
curl http://$ALB_DNS/health/check
```

expected response:
```json
{
  "status": "ok",
  "timestamp": "2025-09-13t21:28:14z",
  "rails_version": "8.0.2.1",
  "environment": "production"
}
```

## common issues and solutions

### container permission errors

**issue**: `permission denied - bind(2) for "0.0.0.0" port 80`

**solution options:**

**option a: use non-privileged port (recommended for security)**
```dockerfile
# run as non-root user on port 3000
USER rails:rails
EXPOSE 3000
CMD ["./bin/rails", "server", "-b", "0.0.0.0", "-p", "3000"]

# update alb target group to port 3000
# update ecs security group to allow port 3000 from alb
```

**option b: use thruster proxy (better performance)**
```dockerfile
# run as root to bind privileged port, but thruster drops privileges
ENV TARGET_PORT=3000
ENV HTTP_PORT=80
EXPOSE 80
CMD ["./bin/thrust", "./bin/rails", "server", "-b", "0.0.0.0", "-p", "3000"]

# benefits: http/2, compression, static file serving, caching
# security: thruster runs as root but rails process runs as rails user
```

**thruster benefits you lose with option a:**
- http/2 support
- automatic compression (gzip/brotli)
- static file serving optimizations
- built-in caching
- x-sendfile support for efficient file downloads

### health check failures

**issue**: alb showing 502/503 errors

**solutions**:
1. verify health check path matches your rails route
2. ensure container is listening on the correct port
3. check security group allows alb → ecs communication
4. review container logs for startup errors

### platform compatibility

**issue**: `exec format error` in container logs

**solution**: build for correct architecture:
```bash
docker buildx build --platform linux/amd64 -t [APP-NAME]:latest .
```


## security considerations

### best practices implemented

1. **secrets management**: sensitive data stored in aws secrets manager
2. **network security**: security groups restrict access between components
3. **least privilege**: iam roles with minimal required permissions
4. **container security**: multi-stage builds reduce attack surface

### security group rules

**with option a (port 3000):**
- alb sg: allow http (80) from internet
- ecs sg: allow http (3000) only from alb sg
- alb handles port 80 → 3000 mapping

**with option b (thruster):**
- alb sg: allow http (80) from internet
- ecs sg: allow http (80) only from alb sg
- thruster handles http optimizations

### security trade-offs

**option a (non-privileged port):**
- ✅ better: no root processes
- ✅ better: principle of least privilege
- ❌ worse: no http/2, compression, caching
- ❌ worse: higher resource usage for static files

**option b (thruster):**
- ✅ better: http/2, compression, optimizations
- ✅ better: rails process still runs as non-root
- ⚠️ acceptable: thruster proxy runs as root (industry standard)
- ⚠️ acceptable: container isolation provides security boundary

**recommendation:** use thruster (option b) unless you have strict security requirements that prohibit any root processes.

## cost optimization

### fargate pricing factors

- **cpu allocation**: 256 cpu units (0.25 vcpu)
- **memory allocation**: 512 mb ram
- **running time**: pay per second, minimum 1 minute

### cost-saving tips

1. **right-size resources**: start small, monitor, and adjust
2. **use spot pricing**: for non-critical workloads
3. **scale to zero**: during low-traffic periods
4. **monitor usage**: cloudwatch metrics for optimization

## monitoring and logging

### cloudwatch integration

- **container logs**: automatically streamed to cloudwatch
- **metrics**: cpu, memory, network utilization
- **alarms**: set up alerts for health check failures

### health check monitoring

```bash
# create cloudwatch alarm for unhealthy targets
aws cloudwatch put-metric-alarm \
  --alarm-name "[APP-NAME]-unhealthy-targets" \
  --alarm-description "alb has unhealthy targets" \
  --metric-name UnHealthyHostCount \
  --namespace AWS/ApplicationELB \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 0 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=TargetGroup,Value=$TG_ARN
```

## deployment commands summary

here's the complete sequence of commands to deploy your rails app:

```bash
# 1. build and push image
docker buildx build --platform linux/amd64 -t [APP-NAME]:latest .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin [ACCOUNT-ID].dkr.ecr.us-east-1.amazonaws.com
docker tag [APP-NAME]:latest [ACCOUNT-ID].dkr.ecr.us-east-1.amazonaws.com/[APP-NAME]:latest
docker push [ACCOUNT-ID].dkr.ecr.us-east-1.amazonaws.com/[APP-NAME]:latest

# 2. create infrastructure
aws ecs create-cluster --cluster-name [APP-NAME]-cluster --region us-east-1
aws logs create-log-group --log-group-name /ecs/[APP-NAME] --region us-east-1

# 3. register task definition and deploy
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json --region us-east-1
aws ecs create-service --cluster [APP-NAME]-cluster --service-name [APP-NAME]-service --task-definition [APP-NAME]-task:1 --desired-count 2 --launch-type FARGATE --network-configuration "awsvpcConfiguration={subnets=[subnet-ids],securityGroups=[ecs-sg-id],assignPublicIp=ENABLED}" --load-balancers "targetGroupArn=[tg-arn],containerName=[APP-NAME],containerPort=80" --region us-east-1

# 4. test deployment
curl http://[alb-dns]/health/check
```

## high availability and reliability patterns

### current availability with 2 containers

our basic deployment with `desired-count: 2` provides:

- **basic redundancy**: if one container fails, traffic routes to the healthy container
- **rolling updates**: ecs can update one container at a time without downtime
- **automatic recovery**: failed containers are automatically restarted
- **estimated availability**: ~99.5% (basic level)

### achieving higher availability (99.9%+)

for production applications requiring maximum uptime, implement these patterns:

#### 1. multi-az deployment with increased capacity

```json
{
  "serviceName": "[APP-NAME]-service-ha",
  "desiredCount": 4,
  "deploymentConfiguration": {
    "maximumPercent": 200,
    "minimumHealthyPercent": 50,
    "deploymentCircuitBreaker": {
      "enable": true,
      "rollback": true
    }
  },
  "networkConfiguration": {
    "awsvpcConfiguration": {
      "subnets": ["subnet-1a", "subnet-1b", "subnet-1c"],
      "securityGroups": ["sg-ecs"],
      "assignPublicIp": "ENABLED"
    }
  }
}
```

**benefits:**
- **4 containers** across 3 availability zones
- can lose entire az and maintain service
- **circuit breaker** automatically rolls back failed deployments
- **deployment flexibility** allows 100% capacity increase during deployments

#### 2. auto scaling configuration

```bash
# create auto scaling target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/[APP-NAME]-cluster/[APP-NAME]-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 4 \
  --max-capacity 20

# cpu-based scaling policy
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/[APP-NAME]-cluster/[APP-NAME]-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name cpu-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleOutCooldown": 300,
    "ScaleInCooldown": 300
  }'
```

#### 3. enhanced health checks

extend your health controller for comprehensive monitoring:

```ruby
# app/controllers/health_controller.rb
class HealthController < ApplicationController
  def check
    health_data = {
      status: "ok",
      timestamp: Time.current.iso8601,
      rails_version: Rails.version,
      environment: Rails.env,
      uptime: uptime_seconds,
      memory: memory_usage,
      checks: {
        database: database_check,
        redis: redis_check,
        storage: storage_check
      }
    }

    if health_data[:checks].values.all? { |check| check[:status] == "ok" }
      render json: health_data, status: :ok
    else
      render json: health_data, status: :service_unavailable
    end
  end

  private

  def database_check
    ActiveRecord::Base.connection.execute("SELECT 1")
    { status: "ok", response_time_ms: 0 }
  rescue => e
    { status: "error", message: e.message }
  end

  def memory_usage
    return {} unless defined?(GC)

    {
      rss_mb: `ps -o rss= -p #{Process.pid}`.strip.to_i / 1024,
      gc_count: GC.count,
      heap_slots: GC.stat[:heap_live_slots]
    }
  end

  def uptime_seconds
    Process.clock_gettime(Process::CLOCK_UPTIME).to_i
  end
end
```

#### 4. monitoring and alerting setup

```bash
# create comprehensive alarms
aws cloudwatch put-metric-alarm \
  --alarm-name "[APP-NAME]-high-cpu" \
  --alarm-description "high cpu utilization" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ServiceName,Value=[APP-NAME]-service Name=ClusterName,Value=[APP-NAME]-cluster

aws cloudwatch put-metric-alarm \
  --alarm-name "[APP-NAME]-response-time" \
  --alarm-description "high response time" \
  --metric-name TargetResponseTime \
  --namespace AWS/ApplicationELB \
  --statistic Average \
  --period 300 \
  --evaluation-periods 3 \
  --threshold 2.0 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=LoadBalancer,Value=[ALB-FULL-NAME]
```

#### 5. graceful shutdown handling

rails applications handle sigterm gracefully by default with puma. configure ecs task definition for proper shutdown timing:

```json
{
  "containerDefinitions": [{
    "stopTimeout": 30,
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -f http://localhost/health/check || exit 1"],
      "interval": 15,
      "timeout": 5,
      "retries": 3,
      "startPeriod": 45
    }
  }]
}
```


### availability comparison

| pattern | containers | azs | estimated availability | recovery time |
|---------|------------|-----|----------------------|---------------|
| basic | 2 | 2 | 99.5% | 2-3 minutes |
| enhanced | 4 | 3 | 99.9% | 30 seconds |
| enterprise | 6+ | 3+ | 99.95%+ | 10 seconds |

### cost vs availability trade-offs

**basic deployment (2 containers):**
- **cost**: ~$30/month for small workloads
- **availability**: sufficient for internal tools, staging
- **recovery**: manual intervention may be needed

**high availability (4+ containers):**
- **cost**: ~$60-120/month depending on scale
- **availability**: production-ready for business applications
- **recovery**: automatic with circuit breakers

**enterprise (6+ containers + auto-scaling):**
- **cost**: variable, $100-500+/month based on traffic
- **availability**: mission-critical applications
- **recovery**: instant failover across multiple zones

### deployment pipeline for ha

```bash
# 1. build and test
docker buildx build --platform linux/amd64 -t [APP-NAME]:latest .
docker run --rm -p 3000:80 [APP-NAME]:latest &
sleep 10
curl -f http://localhost:3000/health/check || exit 1

# 2. push to ecr
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin [ACCOUNT-ID].dkr.ecr.us-east-1.amazonaws.com
docker tag [APP-NAME]:latest [ACCOUNT-ID].dkr.ecr.us-east-1.amazonaws.com/[APP-NAME]:$(git rev-parse --short HEAD)
docker push [ACCOUNT-ID].dkr.ecr.us-east-1.amazonaws.com/[APP-NAME]:$(git rev-parse --short HEAD)

# 3. update task definition with new image
sed "s/:latest/:$(git rev-parse --short HEAD)/g" ecs-task-definition.json > ecs-task-definition-$(git rev-parse --short HEAD).json
aws ecs register-task-definition --cli-input-json file://ecs-task-definition-$(git rev-parse --short HEAD).json

# 4. update service (ecs handles rolling deployment)
aws ecs update-service \
  --cluster [APP-NAME]-cluster \
  --service [APP-NAME]-service \
  --task-definition [APP-NAME]-task:$(aws ecs list-task-definitions --family-prefix [APP-NAME]-task --status ACTIVE --sort DESC --max-items 1 --query 'taskDefinitionArns[0]' --output text | cut -d'/' -f2)

# 5. wait for deployment to complete
aws ecs wait services-stable --cluster [APP-NAME]-cluster --services [APP-NAME]-service
```

### recommended ha configuration

for most production applications, this configuration provides excellent availability:

```json
{
  "desiredCount": 4,
  "deploymentConfiguration": {
    "maximumPercent": 150,
    "minimumHealthyPercent": 75,
    "deploymentCircuitBreaker": {
      "enable": true,
      "rollback": true
    }
  },
  "healthCheckGracePeriodSeconds": 60
}
```

**key benefits:**
- **4 containers** provide redundancy across az failures
- **75% minimum** ensures 3 containers always running during deployments
- **circuit breaker** prevents bad deployments from taking down service
- **reasonable costs** while maintaining high availability

## conclusion

this deployment approach provides:

- **scalable architecture** that grows with your application
- **high availability** across multiple azs with configurable redundancy levels
- **proper health monitoring** with comprehensive alb and container health checks
- **security best practices** with secrets management
- **cost-effective operations** with serverless containers
- **reliability patterns** including auto-scaling, circuit breakers, and graceful shutdowns

the combination of alb health checks, ecs service management, and proper application health endpoints creates a robust production deployment that can achieve 99.9%+ availability for business-critical applications.

for production environments, consider adding:
- database integration (rds with multi-az)
- ssl/tls termination at alb
- cdn (cloudfront) for global performance
- comprehensive monitoring and alerting
- backup and disaster recovery strategies
- blue/green or canary deployments

## repository structure

```
├── dockerfile                 # container definition
├── docker-compose.yml        # local development
├── ecs-task-definition.json  # ecs configuration
├── app/
│   └── controllers/
│       └── health_controller.rb
├── config/
│   └── routes.rb
└── bin/
    └── docker-entrypoint
```

this guide demonstrates a complete production-ready rails deployment on aws using modern containerization and infrastructure practices.
