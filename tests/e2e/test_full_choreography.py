"""End-to-End Choreography and Architecture Integration Test.

Tests the full multi-account data governance flow matching the ADR and architecture diagram:
- Account A: S3 payload upload + Event publication
- Account C: Intake service + 6 choreographic ECS microservices:
    1. account-validation-service
    2. catalog-validation-service
    3. resource-sharing-service
    4. share-acceptance-service
    5. resource-link-service
    6. permissions-service
- DynamoDB state persistence (PK: REQUEST#..., SK: STEP#... and SK: META)
- checkstep-service queries (POST /internal/checkStep)
- Account B: diagnostic-service triggering Step Functions Express and SNS alerts.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import boto3
import pytest
from moto import mock_aws

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Helper to load modules from hyphenated service directory paths
def load_service_module(service_name: str, rel_path: str) -> Any:
    service_dir = BASE_DIR / "services" / service_name
    file_path = service_dir / rel_path
    mod_name = f"{service_name.replace('-', '_')}_{Path(rel_path).stem}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]

    # Purge cached "app" namespace modules so each service isolates its own domain/app packages
    for k in list(sys.modules.keys()):
        if k == "app" or k.startswith("app."):
            del sys.modules[k]

    orig_path = list(sys.path)
    sys.path.insert(0, str(service_dir))
    try:
        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path = orig_path


intake_use_case_mod = load_service_module("intake-service", "app/application/use_cases/intake_request.py")
intake_models_mod = load_service_module("intake-service", "app/domain/models.py")

acc_use_case_mod = load_service_module("account-validation-service", "app/application/use_cases/validate_account.py")
acc_models_mod = load_service_module("account-validation-service", "app/domain/models.py")

cat_use_case_mod = load_service_module("catalog-validation-service", "app/application/use_cases/validate_catalog.py")
cat_models_mod = load_service_module("catalog-validation-service", "app/domain/models.py")

rshare_use_case_mod = load_service_module("resource-sharing-service", "app/application/use_cases/share_resource.py")
rshare_models_mod = load_service_module("resource-sharing-service", "app/domain/models.py")

sacc_use_case_mod = load_service_module("share-acceptance-service", "app/application/use_cases/accept_share.py")
sacc_models_mod = load_service_module("share-acceptance-service", "app/domain/models.py")

rlink_use_case_mod = load_service_module("resource-link-service", "app/application/use_cases/create_resource_link.py")
rlink_models_mod = load_service_module("resource-link-service", "app/domain/models.py")

perm_use_case_mod = load_service_module("permissions-service", "app/application/use_cases/grant_permissions.py")
perm_models_mod = load_service_module("permissions-service", "app/domain/models.py")

diag_use_case_mod = load_service_module("diagnostic-service", "app/application/use_cases/run_diagnostic.py")
diag_models_mod = load_service_module("diagnostic-service", "app/domain/models.py")

from shared.contracts.events import StepName, StepStatus
from shared.infrastructure.dynamodb_step_repository import (
    DynamoDbStepRepository,
)

AWS_REGION = "us-east-1"
TABLE_NAME = "sg-share-governance"
S3_BUCKET = "sg-governance-payloads"


class InMemPublisher:
    def __init__(self):
        self.messages = []

    async def publish(self, message):
        self.messages.append(message)


class InMemNotifier:
    def __init__(self):
        self.notifications = []

    async def publish_notification(self, topic_name, message):
        self.notifications.append((topic_name, message))


class InMemSfnInvoker:
    def __init__(self):
        self.executions = []

    async def start_execution(self, state_machine_name, execution_name, input_payload):
        arn = f"arn:aws:states:{AWS_REGION}:123456789012:execution:{state_machine_name}:{execution_name}"
        self.executions.append(arn)
        return arn


class InMemCheckStepClient:
    def __init__(self, step_repo: DynamoDbStepRepository):
        self._repo = step_repo

    async def check_step(self, request_id: str, attempt_id: str, step_name: str):
        item = await self._repo.find_step(request_id, step_name, attempt_id)
        if not item:
            return {"stepName": step_name, "status": "UNKNOWN"}
        return {
            "requestId": item.get("requestId"),
            "attemptId": item.get("attemptId"),
            "stepName": item.get("stepName"),
            "status": item.get("status"),
            "errorCode": item.get("errorCode"),
        }


@pytest.fixture
def aws_env():
    with mock_aws():
        # Setup DynamoDB
        ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
        ddb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Setup S3 (Account A)
        s3 = boto3.client("s3", region_name=AWS_REGION)
        s3.create_bucket(Bucket=S3_BUCKET)

        yield {"dynamodb": ddb, "s3": s3}


@pytest.mark.asyncio
async def test_full_governance_choreography_success(aws_env):
    ddb = aws_env["dynamodb"]
    s3 = aws_env["s3"]
    step_repo = DynamoDbStepRepository(ddb, TABLE_NAME)

    # 1. AWS Account A: Upload full governance payload to S3
    req_id = "req-e2e-001"
    attempt_id = "attempt-0001"
    corr_id = "corr-e2e-001"

    payload_account_a = {
        "requestId": req_id,
        "attemptId": attempt_id,
        "correlationId": corr_id,
        "producer_account_id": "111122223333",
        "consumer_account_id": "444455556666",
        "database_name": "customer_360",
        "table_names": ["profiles", "transactions"],
        "iam_principal_arn": "arn:aws:iam::444455556666:role/DataScientist",
        "permissions": ["DESCRIBE", "SELECT"],
        "action": "success",
    }
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"payloads/{req_id}.json",
        Body=json.dumps(payload_account_a),
    )

    # 2. AWS Account C: Intake service processes request
    intake_pub = InMemPublisher()
    intake_use_case = intake_use_case_mod.IntakeRequestUseCase(
        repository=step_repo,
        publisher=intake_pub,
    )
    req_obj = intake_models_mod.GovernanceRequest(
        producer_account_id="111122223333",
        consumer_account_id="444455556666",
        database_name="customer_360",
        table_names=["profiles", "transactions"],
        iam_principal_arn="arn:aws:iam::444455556666:role/DataScientist",
        request_id=req_id,
        attempt_id=attempt_id,
        correlation_id=corr_id,
        s3_bucket=S3_BUCKET,
        s3_key=f"payloads/{req_id}.json",
    )
    intake_res = await intake_use_case.execute(req_obj)
    assert intake_res.status == "ACCEPTED"
    assert len(intake_pub.messages) == 1
    event_1 = intake_pub.messages[0]

    # 3. Microservice 1: account-validation-service
    acc_next_pub = InMemPublisher()
    acc_fail_pub = InMemPublisher()
    acc_use_case = acc_use_case_mod.ValidateAccountUseCase(step_repo, acc_next_pub, acc_fail_pub)
    acc_msg = acc_models_mod.IncomingMessage("m1", "rh1", event_1)
    acc_res = await acc_use_case.execute(acc_msg)
    assert acc_res.status.value == "SUCCEEDED"
    assert len(acc_next_pub.messages) == 1
    event_2 = acc_next_pub.messages[0]

    # 4. Microservice 2: catalog-validation-service
    cat_next_pub = InMemPublisher()
    cat_fail_pub = InMemPublisher()
    cat_use_case = cat_use_case_mod.ValidateCatalogUseCase(step_repo, cat_next_pub, cat_fail_pub)
    cat_msg = cat_models_mod.IncomingMessage("m2", "rh2", event_2)
    cat_res = await cat_use_case.execute(cat_msg)
    assert cat_res.status.value == "SUCCEEDED"
    assert len(cat_next_pub.messages) == 1
    event_3 = cat_next_pub.messages[0]

    # 5. Microservice 3: resource-sharing-service
    rshare_next_pub = InMemPublisher()
    rshare_fail_pub = InMemPublisher()
    rshare_use_case = rshare_use_case_mod.ShareResourceUseCase(step_repo, rshare_next_pub, rshare_fail_pub)
    rshare_msg = rshare_models_mod.IncomingMessage("m3", "rh3", event_3)
    rshare_res = await rshare_use_case.execute(rshare_msg)
    assert rshare_res.status.value == "SUCCEEDED"
    assert len(rshare_next_pub.messages) == 1
    event_4 = rshare_next_pub.messages[0]

    # 6. Microservice 4: share-acceptance-service
    sacc_next_pub = InMemPublisher()
    sacc_fail_pub = InMemPublisher()
    sacc_use_case = sacc_use_case_mod.AcceptShareUseCase(step_repo, sacc_next_pub, sacc_fail_pub)
    sacc_msg = sacc_models_mod.IncomingMessage("m4", "rh4", event_4)
    sacc_res = await sacc_use_case.execute(sacc_msg)
    assert sacc_res.status.value == "SUCCEEDED"
    assert len(sacc_next_pub.messages) == 1
    event_5 = sacc_next_pub.messages[0]

    # 7. Microservice 5: resource-link-service
    rlink_next_pub = InMemPublisher()
    rlink_fail_pub = InMemPublisher()
    rlink_use_case = rlink_use_case_mod.CreateResourceLinkUseCase(step_repo, rlink_next_pub, rlink_fail_pub)
    rlink_msg = rlink_models_mod.IncomingMessage("m5", "rh5", event_5)
    rlink_res = await rlink_use_case.execute(rlink_msg)
    assert rlink_res.status.value == "SUCCEEDED"
    assert len(rlink_next_pub.messages) == 1
    event_6 = rlink_next_pub.messages[0]

    # 8. Microservice 6: permissions-service
    perm_comp_pub = InMemPublisher()
    perm_fail_pub = InMemPublisher()
    perm_use_case = perm_use_case_mod.GrantPermissionsUseCase(step_repo, perm_comp_pub, perm_fail_pub)
    perm_msg = perm_models_mod.IncomingMessage("m6", "rh6", event_6)
    perm_res = await perm_use_case.execute(perm_msg)
    assert perm_res.status.value == "SUCCEEDED"
    assert len(perm_comp_pub.messages) == 1
    terminal_event = perm_comp_pub.messages[0]
    assert terminal_event["terminalStatus"] == "SUCCEEDED"

    # 9. Verify DynamoDB state
    meta = await step_repo.find_meta(req_id)
    assert meta["status"] == "SUCCEEDED"

    # 10. Query checkStep for all 6 steps
    for step in [
        "ACCOUNT_VALIDATION",
        "CATALOG_VALIDATION",
        "RESOURCE_SHARING",
        "SHARE_ACCEPTANCE",
        "RESOURCE_LINKS",
        "PERMISSIONS",
    ]:
        item = await step_repo.find_step(req_id, step, attempt_id)
        assert item is not None
        assert item["status"] == "SUCCEEDED"

    # 11. AWS Account B: diagnostic-service consumes terminal event
    sfn_invoker = InMemSfnInvoker()
    check_client = InMemCheckStepClient(step_repo)
    notifier = InMemNotifier()

    diag_use_case = diag_use_case_mod.RunDiagnosticUseCase(sfn_invoker, check_client, notifier)
    diag_msg = diag_models_mod.TerminalEventMessage("m-term", "rh-term", terminal_event)
    outcome = await diag_use_case.execute(diag_msg)

    assert outcome.terminal_status == "SUCCEEDED"
    assert outcome.first_failed_step is None
    assert len(outcome.steps_evaluated) == 6
    assert len(sfn_invoker.executions) == 1
    assert len(notifier.notifications) == 1
    assert notifier.notifications[0][1]["terminalStatus"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_full_governance_choreography_failure_at_step_4(aws_env):
    ddb = aws_env["dynamodb"]
    step_repo = DynamoDbStepRepository(ddb, TABLE_NAME)

    req_id = "req-fail-004"
    attempt_id = "attempt-0001"
    corr_id = "corr-fail-004"

    # Initial event configured to simulate failure at SHARE_ACCEPTANCE
    initial_payload = {
        "requestId": req_id,
        "attemptId": attempt_id,
        "correlationId": corr_id,
        "producer_account_id": "111122223333",
        "consumer_account_id": "444455556666",
        "database_name": "customer_360",
        "table_names": ["profiles"],
        "iam_principal_arn": "arn:aws:iam::444455556666:role/DataScientist",
        "fail_at_step": "SHARE_ACCEPTANCE",
    }

    # Step 1 succeeds
    acc_next_pub = InMemPublisher()
    acc_use_case = acc_use_case_mod.ValidateAccountUseCase(step_repo, acc_next_pub, InMemPublisher())
    await acc_use_case.execute(acc_models_mod.IncomingMessage("m1", "rh1", initial_payload))
    event_2 = acc_next_pub.messages[0]

    # Step 2 succeeds
    cat_next_pub = InMemPublisher()
    cat_use_case = cat_use_case_mod.ValidateCatalogUseCase(step_repo, cat_next_pub, InMemPublisher())
    await cat_use_case.execute(cat_models_mod.IncomingMessage("m2", "rh2", event_2))
    event_3 = cat_next_pub.messages[0]

    # Step 3 succeeds
    rshare_next_pub = InMemPublisher()
    rshare_use_case = rshare_use_case_mod.ShareResourceUseCase(step_repo, rshare_next_pub, InMemPublisher())
    await rshare_use_case.execute(rshare_models_mod.IncomingMessage("m3", "rh3", event_3))
    event_4 = rshare_next_pub.messages[0]

    # Step 4 fails
    sacc_next_pub = InMemPublisher()
    sacc_fail_pub = InMemPublisher()
    sacc_use_case = sacc_use_case_mod.AcceptShareUseCase(step_repo, sacc_next_pub, sacc_fail_pub)
    res_4 = await sacc_use_case.execute(sacc_models_mod.IncomingMessage("m4", "rh4", event_4))
    assert res_4.status.value == "FAILED"
    assert len(sacc_fail_pub.messages) == 1
    term_failure_event = sacc_fail_pub.messages[0]

    # Step 4 recorded as FAILED in DynamoDB
    step_4_item = await step_repo.find_step(req_id, "SHARE_ACCEPTANCE", attempt_id)
    assert step_4_item["status"] == "FAILED"
    assert step_4_item["errorCode"] == "SHARE_ACCEPTANCE_ERROR"

    # Global META updated to FAILED
    meta = await step_repo.find_meta(req_id)
    assert meta["status"] == "FAILED"
    assert meta["failedStep"] == "SHARE_ACCEPTANCE"

    # Diagnostic in Account B reconstructs visual flow and halts at first failure
    sfn_invoker = InMemSfnInvoker()
    check_client = InMemCheckStepClient(step_repo)
    notifier = InMemNotifier()

    diag_use_case = diag_use_case_mod.RunDiagnosticUseCase(sfn_invoker, check_client, notifier)
    outcome = await diag_use_case.execute(
        diag_models_mod.TerminalEventMessage("m-fail", "rh-fail", term_failure_event)
    )

    assert outcome.terminal_status == "FAILED"
    assert outcome.first_failed_step == "SHARE_ACCEPTANCE"
    # Evaluated exactly steps 1, 2, 3 (SUCCEEDED) and 4 (FAILED) -> stopped!
    assert len(outcome.steps_evaluated) == 4
