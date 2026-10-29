#!/usr/bin/env python3
"""Simulation script demonstrating the complete multi-account data governance flow.

Flow (matching architecture diagram & ADR-001):
  [AWS Account A - us-east-1]
    1. Lambda uploads payload to S3 Bucket (sg-governance-payloads)
    2. Lambda sends message to Amazon EventBridge (sg-governance-bus)
    3. EventBridge publishes message to Amazon SNS (sg-share-events-topic)

  [AWS Account C - us-east-1]
    4. Intake service receives event / notification
    6. Intake downloads full payload from S3 (Account A)
    7. Intake triggers ECS choreography (access-validation -> ... -> permissions)

  [AWS Account B - us-west-2]
    4/5. Diagnostic service receives completion/failure event
    6. Verifies payload
    7. Triggers AWS Step Functions Express (GovernanceDiagnosticWorkflow)
    8. Sequentially queries checkStep (POST /internal/checkStep) on ECS
    9. Publishes final diagnostic status to Amazon SNS
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid

import boto3
import urllib.request
import urllib.error

ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
INTAKE_URL = os.getenv("INTAKE_SERVICE_URL", "http://localhost:8001")
CHECKSTEP_URL = os.getenv("CHECKSTEP_SERVICE_URL", "http://localhost")
DIAGNOSTIC_URL = os.getenv("DIAGNOSTIC_SERVICE_URL", "http://localhost:8008")


def main():
    parser = argparse.ArgumentParser(description="Simulate Data Governance Request Flow")
    parser.add_argument("--fail-step", choices=["ACCOUNT_VALIDATION", "CATALOG_VALIDATION", "RESOURCE_SHARING", "SHARE_ACCEPTANCE", "RESOURCE_LINKS", "PERMISSIONS"], help="Simulate failure at a specific step")
    parser.add_argument("--action", default="success", choices=["success", "fail"])
    args = parser.parse_args()

    req_id = f"req-{uuid.uuid4().hex[:8]}"
    attempt_id = "attempt-0001"
    corr_id = f"corr-{uuid.uuid4().hex[:8]}"

    print("\n========================================================")
    print(f">> Starting Governance Request Simulation: {req_id}")
    print("========================================================")

    # 1. Account A: Prepare Payload
    payload = {
        "requestId": req_id,
        "attemptId": attempt_id,
        "correlationId": corr_id,
        "producer_account_id": "111122223333",
        "consumer_account_id": "444455556666",
        "database_name": "enterprise_dw",
        "table_names": ["sales_summary", "dim_customers"],
        "iam_principal_arn": "arn:aws:iam::444455556666:role/BIAnalystRole",
        "permissions": ["DESCRIBE", "SELECT"],
        "action": args.action,
        "fail_at_step": args.fail_step,
    }

    s3_bucket = "sg-governance-payloads"
    s3_key = f"requests/{req_id}.json"
    payload_json = json.dumps(payload, indent=2).encode("utf-8")

    print(f"\n[AWS Account A] Step 1: Uploading payload to S3: s3://{s3_bucket}/{s3_key}")
    s3_uploaded = False

    # Try uploading directly to LocalStack S3 HTTP endpoint
    try:
        s3_url = f"{ENDPOINT_URL.rstrip('/')}/{s3_bucket}/{s3_key}"
        s3_req = urllib.request.Request(
            s3_url,
            data=payload_json,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(s3_req) as s3_resp:
            if s3_resp.status in (200, 201):
                s3_uploaded = True
                print("   [+] Payload uploaded successfully to S3.")
    except Exception as http_exc:
        # Fallback to boto3 client
        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=ENDPOINT_URL,
                region_name="us-east-1",
                aws_access_key_id="test",
                aws_secret_access_key="test",
            )
            s3.put_object(
                Bucket=s3_bucket,
                Key=s3_key,
                Body=payload_json,
            )
            s3_uploaded = True
            print("   [+] Payload uploaded successfully to S3.")
        except Exception as exc:
            print(f"   [-] S3 upload failed or LocalStack unavailable: {exc}")
            print("   [*] Falling back to direct HTTP payload submission...")

    # 2. Account C: Intake Service
    print(f"\n[AWS Account C] Steps 4, 6 & 7: Sending request to Intake Service ({INTAKE_URL}/intake)")
    intake_body = {
        "requestId": req_id,
        "attemptId": attempt_id,
        "correlationId": corr_id,
        "producerAccountId": "111122223333",
        "consumerAccountId": "444455556666",
        "databaseName": "enterprise_dw",
        "tableNames": ["sales_summary", "dim_customers"],
        "iamPrincipalArn": "arn:aws:iam::444455556666:role/BIAnalystRole",
        "action": args.action,
        "failAtStep": args.fail_step,
    }
    if s3_uploaded:
        intake_body["s3Bucket"] = s3_bucket
        intake_body["s3Key"] = s3_key

    req_bytes = json.dumps(intake_body).encode("utf-8")
    req = urllib.request.Request(
        f"{INTAKE_URL}/intake",
        data=req_bytes,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print(f"   [+] Intake Service accepted request: {data}")
    except Exception as exc:
        print(f"   [-] Could not connect to Intake service: {exc}")
        print("   [*] (Ensure docker compose is up: `docker compose up -d --build`)")
        sys.exit(1)

    print("\n>> Waiting for ECS choreography to process through SQS queues...")

    # 3. Query checkStep endpoint with progressive polling
    print(f"\n[Validation] Querying checkStep endpoint ({CHECKSTEP_URL}/internal/checkStep)...")
    steps = [
        "ACCOUNT_VALIDATION",
        "CATALOG_VALIDATION",
        "RESOURCE_SHARING",
        "SHARE_ACCEPTANCE",
        "RESOURCE_LINKS",
        "PERMISSIONS",
    ]

    for step in steps:
        # Poll up to 10 seconds for the step to reach terminal state (SUCCEEDED or FAILED)
        step_status = "UNKNOWN"
        error_info = ""
        for _ in range(10):
            step_req = urllib.request.Request(
                f"{CHECKSTEP_URL}/internal/checkStep",
                data=json.dumps({
                    "requestId": req_id,
                    "attemptId": attempt_id,
                    "stepName": step,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(step_req) as resp:
                    step_data = json.loads(resp.read().decode())
                    step_status = step_data.get("status")
                    if step_data.get("errorCode"):
                        error_info = f" (ErrorCode: {step_data.get('errorCode')})"
                    if step_status in ("SUCCEEDED", "FAILED"):
                        break
            except urllib.error.HTTPError:
                pass
            time.sleep(1)

        print(f"   - Step {step:20s}: {step_status}{error_info}")
        if step_status == "FAILED":
            print(f"\n[AWS Account B] Choreography halted at step {step} as expected by simulation.")
            print(f"[AWS Account B] Visual diagnostic workflow triggered in AWS Step Functions.")
            break
        elif step_status not in ("SUCCEEDED", "FAILED"):
            print(f"   [!] Step {step} timed out waiting for processing.")
            break

    print("\n========================================================")
    print(">> Simulation completed.")
    print("========================================================\n")


if __name__ == "__main__":
    main()
