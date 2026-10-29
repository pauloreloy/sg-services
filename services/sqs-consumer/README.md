# sqs-consumer

Microserviço em **Python + FastAPI** que consome mensagens da fila SQS
`sg-share-queue`, decide sucesso/falha com base na chave `action` do payload,
persiste um registro de auditoria no **DynamoDB** e republica o resultado em
uma das duas filas de saída (`sg-share-success-queue` ou
`sg-share-failure-queue`).

O projeto segue **arquitetura hexagonal (ports & adapters)**: o domínio e os
casos de uso não conhecem AWS/boto3/FastAPI; toda a infraestrutura é
conectada através de interfaces (`ports`) e implementações concretas
(`adapters`).

> Este serviço grava os registros consultados pelo
> [checkstep-service](../checkstep-service), na mesma tabela DynamoDB.

## Arquitetura

```
app/
  domain/                 # Núcleo de negócio (sem dependências externas)
    models.py             # Entidades: IncomingMessage, ProcessingRecord
    enums.py              # ProcessingStatus (SUCCESS / FAILURE)
    exceptions.py         # Erros de domínio
    ports/                # Interfaces (abstrações) que a aplicação depende
      queue_consumer.py
      queue_publisher.py
      processing_record_repository.py

  application/             # Orquestração dos casos de uso
    dto.py
    use_cases/
      process_message.py  # Regra de negócio: decide sucesso/falha, persiste e publica

  infrastructure/          # Adapters concretos (detalhes técnicos)
    config.py              # Settings (env vars / .env)
    aws_clients.py         # Factories boto3 (SQS, DynamoDB)
    container.py           # Composition root (injeção de dependências)
    adapters/
      sqs_consumer_adapter.py
      sqs_publisher_adapter.py
      dynamodb_repository.py
    api/
      health.py            # Endpoints HTTP (/health, /ready)
      schemas.py

  workers/
    consumer_worker.py      # Loop de polling em background (asyncio)

main.py                     # Entrypoint FastAPI (sobe o worker no lifespan)
```

### Regra de negócio

Toda mensagem recebida deve conter a chave `action` no payload (JSON):

| `action`                         | Resultado  |
|-----------------------------------|------------|
| `"fail"` (case-insensitive)       | `FAILURE`  |
| qualquer outro valor (ex.: `"success"`) | `SUCCESS` |
| chave ausente/vazia ou payload inválido | `FAILURE` (nunca descartado silenciosamente) |

Em **ambos os casos** (sucesso ou falha):
1. O payload recebido é logado/impresso no console.
2. Um `ProcessingRecord` é persistido na tabela DynamoDB
   (`sg-share-processing-records`). Se o payload contiver `grant_id`, ele é
   gravado como **atributo de topo** do item (além de continuar dentro do
   `payload` serializado) — é isso que permite ao
   [checkstep-service](../checkstep-service) consultar o status rapidamente
   via GSI, sem fazer *scan* na tabela.
3. O resultado é publicado na fila de saída correspondente
   (`sg-share-success-queue` ou `sg-share-failure-queue`).
4. A mensagem original é removida (`ack`) de `sg-share-queue`.

> Apenas falhas **técnicas** (erro ao acessar AWS, DynamoDB fora do ar etc.)
> fazem a mensagem **não** ser confirmada, permitindo retry/DLQ pelo próprio
> SQS. Falhas de **negócio** (`action=fail`) são tratadas como processamento
> bem-sucedido do ponto de vista técnico.

## Como rodar localmente

A forma recomendada é via o `docker-compose.yml` na raiz do monorepo (sobe
LocalStack + os 2 microserviços de uma vez). Veja o
[README principal](../../README.md).

Para rodar **apenas este serviço** sem Docker:

1. Suba apenas o LocalStack (via Docker) para ter SQS/DynamoDB disponíveis:
   ```bash
   cd ../.. && docker compose up -d localstack
   ```
2. Crie um virtualenv e instale as dependências:
   ```bash
   cd services/sqs-consumer
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
3. Copie o `.env.example` para `.env`:
   ```bash
   cp .env.example .env
   ```
4. Rode a aplicação:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

## Testes

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
```

- `tests/unit`: testam a regra de negócio (`ProcessMessageUseCase`) com
  adapters fake (sem nenhuma dependência de AWS).
- `tests/integration`: testam os adapters reais (SQS/DynamoDB) usando a
  biblioteca `moto`, que mocka a AWS em memória (não requer Docker).

## Variáveis de ambiente

Veja [.env.example](.env.example) para a lista completa. As mais relevantes:

| Variável | Padrão | Descrição |
|---|---|---|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | Endpoint do LocalStack. Deixe vazio para AWS real. |
| `SQS_SOURCE_QUEUE_NAME` | `sg-share-queue` | Fila consumida pelo worker |
| `SQS_SUCCESS_QUEUE_NAME` | `sg-share-success-queue` | Fila de destino em caso de sucesso |
| `SQS_FAILURE_QUEUE_NAME` | `sg-share-failure-queue` | Fila de destino em caso de falha |
| `DYNAMODB_TABLE_NAME` | `sg-share-processing-records` | Tabela de auditoria |
| `SQS_WAIT_TIME_SECONDS` | `10` | Long polling do SQS |
