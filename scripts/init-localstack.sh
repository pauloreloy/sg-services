#!/usr/bin/env bash
# Provisions the AWS resources used by the service (SQS queues + DynamoDB
# table) against the LocalStack container. Mounted into LocalStack's
# /etc/localstack/init/ready.d/ so it runs automatically once LocalStack is
# ready, right after the containers come up via docker-compose.
set -euo pipefail

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="${AWS_REGION:-us-east-1}"

ENDPOINT_URL="http://localhost:4566"

SOURCE_QUEUE_NAME="${SQS_SOURCE_QUEUE_NAME:-sg-share-queue}"
SUCCESS_QUEUE_NAME="${SQS_SUCCESS_QUEUE_NAME:-sg-share-success-queue}"
FAILURE_QUEUE_NAME="${SQS_FAILURE_QUEUE_NAME:-sg-share-failure-queue}"
DYNAMODB_TABLE_NAME="${DYNAMODB_TABLE_NAME:-sg-share-processing-records}"
DYNAMODB_GRANT_ID_INDEX_NAME="${DYNAMODB_GRANT_ID_INDEX_NAME:-grant_id-processed_at-index}"

# Prefer the bundled `awslocal` wrapper (ships with the LocalStack image);
# fall back to plain `aws` with an explicit endpoint otherwise.
if command -v awslocal >/dev/null 2>&1; then
  awslocal() { command awslocal "$@"; }
else
  awslocal() { aws --endpoint-url="${ENDPOINT_URL}" "$@"; }
fi

echo ">> Creating SQS queues..."
for queue in "${SOURCE_QUEUE_NAME}" "${SUCCESS_QUEUE_NAME}" "${FAILURE_QUEUE_NAME}"; do
  echo "   - ${queue}"
  awslocal sqs create-queue --queue-name "${queue}" >/dev/null
done

echo ">> Creating DynamoDB table '${DYNAMODB_TABLE_NAME}' (with GSI '${DYNAMODB_GRANT_ID_INDEX_NAME}')..."
if awslocal dynamodb describe-table --table-name "${DYNAMODB_TABLE_NAME}" >/dev/null 2>&1; then
  echo "   - table already exists, skipping."
else
  awslocal dynamodb create-table \
    --table-name "${DYNAMODB_TABLE_NAME}" \
    --attribute-definitions \
        AttributeName=record_id,AttributeType=S \
        AttributeName=grant_id,AttributeType=S \
        AttributeName=processed_at,AttributeType=S \
    --key-schema AttributeName=record_id,KeyType=HASH \
    --global-secondary-indexes \
        "[{\"IndexName\": \"${DYNAMODB_GRANT_ID_INDEX_NAME}\", \
            \"KeySchema\": [{\"AttributeName\": \"grant_id\", \"KeyType\": \"HASH\"}, \
                            {\"AttributeName\": \"processed_at\", \"KeyType\": \"RANGE\"}], \
            \"Projection\": {\"ProjectionType\": \"ALL\"}}]" \
    --billing-mode PAY_PER_REQUEST >/dev/null
fi

echo ">> LocalStack resources provisioned successfully."
