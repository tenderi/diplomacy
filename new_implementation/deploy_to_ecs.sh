#!/usr/bin/env bash
set -euo pipefail

# Configurable variables
AWS_ACCOUNT_ID=511302509360
AWS_REGION=eu-west-1
AWS_PROFILE="PS-sandbox"
ECR_REPO=diplomacy-app
CLUSTER=diplomacy-cluster
SERVICE=diplomacy-app-service
TASK_DEF_JSON=ecs-task-definition.json
IMAGE_NAME=diplomacy-app
TAG=${1:-latest}

ECR_IMAGE="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$TAG"

# Authenticate Docker to ECR
aws ecr get-login-password --profile $AWS_PROFILE --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build the Docker image
DOCKER_BUILDKIT=1 docker build -t $IMAGE_NAME:$TAG .

docker tag $IMAGE_NAME:$TAG $ECR_IMAGE

docker push $ECR_IMAGE

# Register the ECS task definition
aws ecs register-task-definition --profile $AWS_PROFILE --cli-input-json file://$TASK_DEF_JSON

# Get the latest revision number
REVISION=$(aws ecs describe-task-definition --profile $AWS_PROFILE --task-definition $IMAGE_NAME | jq -r '.taskDefinition.revision')

# Update the ECS service to use the new revision
echo "Updating ECS service to use $IMAGE_NAME:$TAG (revision $REVISION)"
aws ecs update-service --profile $AWS_PROFILE \
  --cluster $CLUSTER \
  --service $SERVICE \
  --task-definition $IMAGE_NAME

echo "Deployment triggered. Monitor ECS and CloudWatch for status." 