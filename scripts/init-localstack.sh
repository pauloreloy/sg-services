#!/usr/bin/env bash
# Provisions the AWS resources used across the modernized governance platform
# against the LocalStack container (SQS queues, DLQs, DynamoDB tables, S3 bucket,
# SNS topics, EventBridge bus and Step Functions Express state machine).
set -euo pipefail

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="${AWS_REGION:-us-east-1}"

ENDPOINT_URL="http://localhost:4566"

# Prefer the bundled `awslocal` wrapper (ships with the LocalStack image);
# fall back to plain `aws` with an explicit endpoint otherwise.
if command -v awslocal >/dev/null 2>&1; then
  awslocal() { command awslocal "$@"; }
else
  awslocal() { aws --endpoint-url="${ENDPOINT_URL}" "$@"; }
fi

echo ">> ========================================================"
echo ">> Provisioning Modernized Data Governance AWS Resources..."
echo ">> ========================================================"

# --- 1. S3 Bucket (Account A Payload Storage) ---
echo ">> Creating S3 Buckets..."
awslocal s3 mb s3://sg-governance-payloads 2>/dev/null || true

# --- 2. SNS Topics ---
echo ">> Creating SNS Topics..."
awslocal sns create-topic --name sg-share-events-topic >/dev/null 2>&1 || true
awslocal sns create-topic --name sg-governance-notifications >/dev/null 2>&1 || true

# --- 3. EventBridge Event Bus ---
echo ">> Creating EventBridge Event Bus..."
awslocal events create-event-bus --name sg-governance-bus >/dev/null 2>&1 || true

# --- 4. SQS Queues & DLQs ---
echo ">> Creating SQS Queues & Dead-Letter Queues (DLQs)..."

QUEUES=(
  "access-validation"
  "database-validation"
  "resource-sharing"
  "share-acceptance"
  "resource-links"
  "permissions"
  "workflow-completed"
  "workflow-failed"
  "sg-share-queue"
  "sg-share-success-queue"
  "sg-share-failure-queue"
)

for q in "${QUEUES[@]}"; do
  # Create DLQ for step queues
  if [[ "$q" != "sg-share-"* ]]; then
    awslocal sqs create-queue --queue-name "${q}-dlq" >/dev/null 2>&1 || true
  fi
  awslocal sqs create-queue --queue-name "${q}" >/dev/null 2>&1 || true
  echo "   - ${q}"
done

# --- 5. DynamoDB Tables ---
echo ">> Creating DynamoDB Tables..."

# Modern governance table (PK, SK as per ADR 5.5)
GOVERNANCE_TABLE="${DYNAMODB_GOVERNANCE_TABLE_NAME:-sg-share-governance}"
if awslocal dynamodb describe-table --table-name "${GOVERNANCE_TABLE}" >/dev/null 2>&1; then
  echo "   - Table '${GOVERNANCE_TABLE}' already exists, skipping."
else
  echo "   - Creating '${GOVERNANCE_TABLE}' (PK, SK)..."
  awslocal dynamodb create-table \
    --table-name "${GOVERNANCE_TABLE}" \
    --attribute-definitions \
        AttributeName=PK,AttributeType=S \
        AttributeName=SK,AttributeType=S \
    --key-schema \
        AttributeName=PK,KeyType=HASH \
        AttributeName=SK,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST >/dev/null
fi

# Legacy processing records table
LEGACY_TABLE="${DYNAMODB_TABLE_NAME:-sg-share-processing-records}"
LEGACY_INDEX="${DYNAMODB_GRANT_ID_INDEX_NAME:-grant_id-processed_at-index}"
if awslocal dynamodb describe-table --table-name "${LEGACY_TABLE}" >/dev/null 2>&1; then
  echo "   - Table '${LEGACY_TABLE}' already exists, skipping."
else
  echo "   - Creating '${LEGACY_TABLE}' (record_id + GSI)..."
  awslocal dynamodb create-table \
    --table-name "${LEGACY_TABLE}" \
    --attribute-definitions \
        AttributeName=record_id,AttributeType=S \
        AttributeName=grant_id,AttributeType=S \
        AttributeName=processed_at,AttributeType=S \
    --key-schema AttributeName=record_id,KeyType=HASH \
    --global-secondary-indexes \
        "[{\"IndexName\": \"${LEGACY_INDEX}\", \
            \"KeySchema\": [{\"AttributeName\": \"grant_id\", \"KeyType\": \"HASH\"}, \
                            {\"AttributeName\": \"processed_at\", \"KeyType\": \"RANGE\"}], \
            \"Projection\": {\"ProjectionType\": \"ALL\"}}]" \
    --billing-mode PAY_PER_REQUEST >/dev/null
fi

# --- 6. Step Functions Express State Machine ---
echo ">> Creating Step Functions Express State Machine..."
ROLE_ARN="arn:aws:iam::000000000000:role/StepFunctionsExecutionRole"
# Note: AWS production uses step_functions/governance_diagnostic_workflow.asl.json with arn:aws:states:::http:invoke.
# LocalStack Community Edition doesn't mock the 'http' task integration; we register the workflow states natively.
SFN_DEF='{"Comment": "Visual diagnostic reconstruction workflow for AWS Data Governance Choreography (ADR-001)", "StartAt": "CheckTerminalStatus", "States": {"CheckTerminalStatus": {"Type": "Choice", "Choices": [{"Variable": "$.terminalStatus", "StringEquals": "SUCCEEDED", "Next": "Success"}, {"Variable": "$.terminalStatus", "StringEquals": "FAILED", "Next": "Failure"}], "Default": "DiagnosticError"}, "Success": {"Type": "Succeed"}, "Failure": {"Type": "Fail", "Error": "ProvisioningFailed", "Cause": "Uma etapa da coreografia foi registrada como FAILED."}, "DiagnosticError": {"Type": "Fail", "Error": "DiagnosticFailed", "Cause": "Não foi possível confirmar o estado da coreografia."}}}'

awslocal stepfunctions create-state-machine \
  --name "GovernanceDiagnosticWorkflow" \
  --type "EXPRESS" \
  --role-arn "$ROLE_ARN" \
  --definition "$SFN_DEF" >/dev/null 2>&1 || true
echo "   - State Machine 'GovernanceDiagnosticWorkflow' created."

echo ">> ========================================================"
echo ">> All LocalStack resources provisioned successfully."
echo ">> ========================================================"
