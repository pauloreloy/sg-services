# ShareGrant — Plataforma de Governança de Dados AWS

Plataforma modernizada de governança de dados e concessão de acesso multi-conta em **AWS Lake Formation**, seguindo a **ADR-001** e a arquitetura distribuída multi-conta.

O ecossistema é composto por microserviços em **Python + FastAPI**, implementados em **arquitetura hexagonal (ports & adapters)**, orquestração coreografada assíncrona via **Amazon SQS**, persistência transacional e autoritativa no **Amazon DynamoDB**, e diagnóstico visual retrospectivo através de **AWS Step Functions Express**.

---

## 1. Visão Geral da Arquitetura Multi-Conta

A plataforma atende à arquitetura distribuída composta por 3 contas AWS:

![Diagrama da Arquitetura Multi-Conta](docs/assets/architecture-diagram.jpg)

### Papéis das Contas AWS

| Conta | Localização | Responsabilidade | Componentes AWS |
|---|---|---|---|
| **AWS Account A** | `us-east-1` | **Producer / Requester**: Armazena o payload completo da solicitação de acesso e publica eventos de notificação. | AWS Lambda, S3 Bucket (`sg-governance-payloads`), EventBridge (`sg-governance-bus`), SNS (`sg-share-events-topic`). |
| **AWS Account C** | `us-east-1` | **Coreografia de Governança (ECS / Fargate)**: Obtém o payload do S3 da Account A e executa a esteira de governança desacoplada via SQS. | ECS/Fargate, SQS (filas de etapa + DLQs), DynamoDB (`sg-share-governance`), Lake Formation, Glue Catalog, RAM. |
| **AWS Account B** | `us-west-2` | **Diagnóstico Visual e Auditoria**: Consome eventos terminais, inicia a execução de diagnóstico e reconstrói o percurso visual. | Amazon SQS, AWS Lambda / Worker, **AWS Step Functions Express**, Amazon SNS (`sg-governance-notifications`). |

---

## 2. Microserviços da Plataforma

Todos os microserviços seguem rigorosamente a mesma estrutura de diretórios e padrões arquiteturais hexagonais:

| Microserviço | Responsabilidade de Negócio | Fila de Entrada (SQS) | Fila de Saída (SQS) | Porta Host |
|---|---|---|---|---|
| [services/intake-service](services/intake-service) | API de entrada: aceita solicitações diretas ou referências a payloads no S3 (Account A), grava estado inicial no DynamoDB e inicia o fluxo. | — (`POST /intake`) | `access-validation` | `8001` |
| [services/account-validation-service](services/account-validation-service) | **Etapa 1**: Valida contas solicitante/produtora/consumidora e elegibilidade organizacional. | `access-validation` | `database-validation` (ou `workflow-failed`) | `8002` |
| [services/catalog-validation-service](services/catalog-validation-service) | **Etapa 2**: Valida database, tabelas, metadados e diferencia ownership de dados do catálogo. | `database-validation` | `resource-sharing` (ou `workflow-failed`) | `8003` |
| [services/resource-sharing-service](services/resource-sharing-service) | **Etapa 3**: Cria o compartilhamento cross-account via AWS RAM e Lake Formation. | `resource-sharing` | `share-acceptance` (ou `workflow-failed`) | `8004` |
| [services/share-acceptance-service](services/share-acceptance-service) | **Etapa 4**: Avalia aceite condicional de compartilhamento cross-account / AWS Organization. | `share-acceptance` | `resource-links` (ou `workflow-failed`) | `8005` |
| [services/resource-link-service](services/resource-link-service) | **Etapa 5**: Cria Resource Links no Glue Data Catalog da conta consumidora. | `resource-links` | `permissions` (ou `workflow-failed`) | `8006` |
| [services/permissions-service](services/permissions-service) | **Etapa 6**: Concede permissões finais de Lake Formation e dispara evento terminal de conclusão. | `permissions` | `workflow-completed` (ou `workflow-failed`) | `8007` |
| [services/checkstep-service](services/checkstep-service) | API de consulta de status de cada etapa (`POST /internal/checkStep` e `POST /checkStep`) para a Step Functions Express. | — | — | `80` (container: `8080`) |
| [services/diagnostic-service](services/diagnostic-service) | Consome filas terminais, inicia a Step Functions Express (`GovernanceDiagnosticWorkflow`) e emite alertas SNS. | `workflow-completed`, `workflow-failed` | — (`POST /diagnose`) | `8008` |
| [services/sqs-consumer](services/sqs-consumer) | Consumer de compatibilidade legada da fila `sg-share-queue`. | `sg-share-queue` | `sg-share-success-queue`, `sg-share-failure-queue` | `8000` |

---

## 3. Modelo de Dados DynamoDB (ADR 5.5)

A tabela principal de governança é a `sg-share-governance`:

- **Partição (PK):** `REQUEST#<requestId>`
- **Ordenação (SK):** `META` ou `STEP#<stepName>#ATTEMPT#<attemptId>`

Campos principais por item de etapa:
- `requestId`, `attemptId`, `stepName`, `status` (`RUNNING`, `SUCCEEDED`, `FAILED`)
- `startedAt`, `completedAt` (ISO-8601 UTC)
- `errorCode`, `message` (sanitizados para operação)
- `correlationId`, `idempotencyKey` (`<requestId>#<attemptId>#<stepName>`)
- `resourceRef` (metadados seguros do recurso criado/validado)

---

## 4. Reconstrução Visual pós-processamento (Step Functions Express)

Conforme a **ADR-001**:
- A Step Functions Express **não orquestra** os microserviços em tempo real.
- Quando o workflow emite `WorkflowCompleted` ou `WorkflowFailed`, a máquina de estados Express é iniciada com nome determinístico derivado do hash de `requestId + attemptId + terminalStatus`.
- A máquina executa sequencialmente:
  1. `CheckAccountValidation` -> `EvaluateAccountValidation`
  2. `CheckCatalogValidation` -> `EvaluateCatalogValidation`
  3. `CheckResourceSharing` -> `EvaluateResourceSharing`
  4. `CheckShareAcceptance` -> `EvaluateShareAcceptance`
  5. `CheckResourceLinks` -> `EvaluateResourceLinks`
  6. `CheckPermissions` -> `EvaluatePermissions`
- Em caso de falha em qualquer etapa, a máquina desvia imediatamente para o ramo `Failure`, evidenciando a primeira etapa que falhou. Caso todas sucedam, finaliza no ramo `Success`.
- O arquivo ASL completo está disponível em [`step_functions/governance_diagnostic_workflow.asl.json`](step_functions/governance_diagnostic_workflow.asl.json).

---

## 5. Como Executar com Docker Compose

### Pré-requisitos
- Docker e Docker Compose instalados.

### Subindo todo o ecossistema
```bash
docker compose up -d --build
```

O `docker-compose.yml` inicia:
1. **LocalStack 3.8**: emulando SQS, DynamoDB, S3, SNS, EventBridge e Step Functions. Executa automaticamente [`scripts/init-localstack.sh`](scripts/init-localstack.sh).
2. Todos os microserviços e a API `checkStep`.

### Testando o fluxo completo com o script de simulação
O script [`scripts/simulate_request.py`](scripts/simulate_request.py) executa a simulação completa:
```bash
# 1. Simulação de fluxo com sucesso em todas as etapas:
python3 scripts/simulate_request.py

# 2. Simulação de falha controlada na etapa 4 (SHARE_ACCEPTANCE):
python3 scripts/simulate_request.py --fail-step SHARE_ACCEPTANCE
```

### Consultando o status de uma etapa diretamente via HTTP:
```bash
curl -X POST http://localhost/internal/checkStep \
  -H "Content-Type: application/json" \
  -d '{
    "requestId": "req-12345",
    "attemptId": "attempt-0001",
    "stepName": "RESOURCE_LINKS"
  }'
```

---

## 6. Executando os Testes Automatizados

Cada microserviço possui testes unitários e de integração independentes (utilizando `moto` para simulação in-memory dos serviços AWS, sem dependência do Docker):

```bash
# Rodar todos os testes de todos os microserviços e testes ponta-a-ponta (E2E):
for s in services/*; do
  if [ -d "$s/tests" ]; then
    echo "=== Running tests for $s ==="
    PYTHONPATH="$s:." .venv/bin/pytest "$s/tests"
  fi
done

# Rodar testes End-to-End da coreografia:
PYTHONPATH=. .venv/bin/pytest tests/e2e
```

Para mais detalhes da decisão arquitetural, consulte [docs/ADR-001-Modernizacao-Plataforma-Governanca-Dados.md](docs/ADR-001-Modernizacao-Plataforma-Governanca-Dados.md).
