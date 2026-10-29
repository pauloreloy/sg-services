# ShareGrant — Microserviços

Monorepo com dois microserviços **Python + FastAPI**, seguindo **arquitetura
hexagonal (ports & adapters)**, que compartilham a mesma tabela DynamoDB:

| Serviço | Responsabilidade | Porta (host) |
|---|---|---|
| [services/sqs-consumer](services/sqs-consumer) | Consome a fila SQS `sg-share-queue`, decide sucesso/falha pela chave `action`, persiste um registro de auditoria no DynamoDB e republica em `sg-share-success-queue` / `sg-share-failure-queue`. | `8000` |
| [services/checkstep-service](services/checkstep-service) | Expõe `POST /checkStep` (body `{ "grant_id": "..." }`) e retorna o status mais recente gravado no DynamoDB para aquele `grant_id`. | `80` |

```
.
├── docker-compose.yml          # Orquestra LocalStack + os 2 microserviços
├── scripts/init-localstack.sh  # Cria filas SQS + tabela DynamoDB (com GSI)
├── services/
│   ├── sqs-consumer/           # Microserviço consumer (detalhes: README próprio)
│   └── checkstep-service/      # Microserviço de consulta (detalhes: README próprio)
```

## Como os serviços se conectam

Ambos os serviços leem/escrevem na mesma tabela DynamoDB
`sg-share-processing-records`:

- O **sqs-consumer** grava `grant_id` como atributo de topo do item (extraído
  do payload da mensagem), além do `payload` completo serializado.
- O **checkstep-service** consulta um **GSI** (`grant_id-processed_at-index`)
  — partição `grant_id`, ordenação `processed_at` — para buscar o registro
  mais recente de um `grant_id` com uma única `Query` (sem *scan* na tabela).
  Quando há reprocessamento (múltiplos registros para o mesmo `grant_id`),
  o `checkStep` sempre retorna o **mais recente**.

## Subindo tudo com Docker Compose (recomendado)

Pré-requisitos: Docker e Docker Compose.

```bash
docker compose up -d --build
```

Isso sobe:
- **localstack**: emula SQS e DynamoDB. Ao ficar pronto, executa
  [scripts/init-localstack.sh](scripts/init-localstack.sh) automaticamente,
  criando as filas e a tabela DynamoDB (já com o GSI usado pelo `checkStep`).
- **sqs-consumer**: `http://localhost:8000` (worker de consumo em background).
- **checkstep-service**: `http://localhost:80` (`POST /checkStep`).

> **Sobre a porta 80**: por segurança, o container do `checkstep-service` roda
> como usuário não-root e escuta internamente na porta `8080`; o
> `docker-compose.yml` mapeia `80 -> 8080` no host. Do ponto de vista de quem
> consome a API, o serviço está exposto normalmente em `http://localhost/checkStep`.

### Testando o fluxo completo

```bash
# 1) Health checks
curl http://localhost:8000/health
curl http://localhost/health

# 2) Envia uma mensagem de sucesso para a fila de origem
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1
QUEUE_URL=$(aws --endpoint-url=http://localhost:4566 sqs get-queue-url \
  --queue-name sg-share-queue --query QueueUrl --output text)

aws --endpoint-url=http://localhost:4566 sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body '{"action": "success", "grant_id": "grant-123", "amount": 500}'

# 3) Consulta o status gravado via checkStep
curl -X POST http://localhost/checkStep \
  -H "Content-Type: application/json" \
  -d '{"grant_id": "grant-123"}'
# => {"grant_id":"grant-123","status":"SUCCESS", ...}

# 4) grant_id inexistente retorna 404
curl -i -X POST http://localhost/checkStep \
  -H "Content-Type: application/json" \
  -d '{"grant_id": "nao-existe"}'
```

Para parar e remover os containers/volumes:

```bash
docker compose down -v
```

## Documentação detalhada de cada serviço

- [services/sqs-consumer/README.md](services/sqs-consumer/README.md) —
  arquitetura, regra de negócio, execução sem Docker, testes.
- [services/checkstep-service/README.md](services/checkstep-service/README.md) —
  arquitetura, contrato da API `/checkStep`, execução sem Docker, testes.

## Rodando/testando cada serviço isoladamente (sem Docker)

Cada serviço tem seu próprio virtualenv, `requirements*.txt` e suíte de
testes independente (adapters testados com `moto`, sem precisar de Docker):

```bash
# sqs-consumer
cd services/sqs-consumer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v

# checkstep-service
cd services/checkstep-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
```

## Deploy em AWS real

Em ambos os serviços, basta remover/deixar vazio `AWS_ENDPOINT_URL` e
fornecer credenciais reais (ou uma IAM Role, se rodando em ECS/EKS/EC2)
apontando para os recursos já existentes na AWS (mesmos nomes de fila/tabela,
incluindo o GSI `grant_id-processed_at-index`).
