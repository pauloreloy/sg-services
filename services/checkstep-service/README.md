# checkstep-service

Microserviço em **Python + FastAPI** que expõe o endpoint `POST /checkStep`:
dado um `grant_id`, retorna o status (`SUCCESS`/`FAILURE`) mais recente
gravado no DynamoDB pelo [sqs-consumer](../sqs-consumer) para aquele grant.

Segue **arquitetura hexagonal (ports & adapters)**: o domínio e o caso de uso
não conhecem AWS/boto3/FastAPI; a infraestrutura é conectada através de
interfaces (`ports`) e implementações concretas (`adapters`).

## Arquitetura

```
app/
  domain/
    models.py              # Entidade GrantStatus
    enums.py               # ProcessingStatus (SUCCESS / FAILURE)
    exceptions.py          # GrantNotFoundError
    ports/
      grant_status_repository.py  # Interface do repositório de consulta

  application/
    dto.py
    use_cases/
      get_grant_status.py  # Regra: busca o registro mais recente ou levanta GrantNotFoundError

  infrastructure/
    config.py               # Settings (env vars / .env)
    aws_clients.py           # Factory boto3 (DynamoDB)
    container.py             # Composition root (injeção de dependências)
    adapters/
      dynamodb_grant_status_repository.py  # Query no GSI grant_id-processed_at-index
    api/
      check_step.py          # POST /checkStep
      health.py               # GET /health
      schemas.py
      dependencies.py         # Ponte entre o container e o Depends() do FastAPI

main.py                       # Entrypoint FastAPI
```

## Contrato da API

### `POST /checkStep`

**Request body:**
```json
{ "grant_id": "grant-123" }
```

**Resposta — 200 OK (grant_id encontrado):**
```json
{
  "grant_id": "grant-123",
  "status": "SUCCESS",
  "action": "success",
  "reason": null,
  "record_id": "34164280-ff0f-48a0-9749-116901de674a",
  "message_id": "a9f73675-ad7c-4dec-9899-8c8c3307c30b",
  "processed_at": "2026-10-29T02:43:16.109190Z"
}
```

**Resposta — 404 Not Found (grant_id sem registro):**
```json
{ "detail": "No record found for grant_id='grant-123'." }
```

**Resposta — 422 Unprocessable Entity** (body inválido, ex.: `grant_id`
ausente).

> Quando existem **múltiplos registros** para o mesmo `grant_id` (ex.: a
> mensagem foi reprocessada), o `checkStep` sempre retorna o **mais recente**
> (por `processed_at`).

### `GET /health`

Liveness probe simples (`{"status": "ok", "app_name": "..."}`).

## Como a consulta é feita (DynamoDB)

A tabela `sg-share-processing-records` possui um **GSI**
`grant_id-processed_at-index` (partição: `grant_id`, ordenação:
`processed_at`), criado pelo [sqs-consumer](../sqs-consumer) via
[scripts/init-localstack.sh](../../scripts/init-localstack.sh). O
`checkstep-service` executa uma única `Query` nesse índice, ordenada
descendente por `processed_at` com `Limit=1` — **O(1)**, sem nenhum *scan* na
tabela.

## Porta 80 e segurança do container

Por boas práticas, o processo `uvicorn` roda como **usuário não-root** dentro
do container, escutando na porta alta `8080` (bind em portas < 1024 exigiria
root, o que é evitado). O [docker-compose.yml](../../docker-compose.yml) na
raiz do monorepo mapeia `host:80 -> container:8080`, então, de fora, o
serviço continua acessível normalmente em `http://localhost/checkStep`.

## Como rodar localmente

A forma recomendada é via o `docker-compose.yml` na raiz do monorepo (sobe
LocalStack + os 2 microserviços de uma vez). Veja o
[README principal](../../README.md).

Para rodar **apenas este serviço** sem Docker:

1. Suba apenas o LocalStack (via Docker) para ter o DynamoDB disponível:
   ```bash
   cd ../.. && docker compose up -d localstack
   ```
2. Crie um virtualenv e instale as dependências:
   ```bash
   cd services/checkstep-service
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
3. Copie o `.env.example` para `.env`:
   ```bash
   cp .env.example .env
   ```
4. Rode a aplicação (porta alta, sem precisar de root):
   ```bash
   uvicorn main:app --reload --port 8080
   ```

## Testes

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
```

- `tests/unit`: testa `GetGrantStatusUseCase` com um repositório fake (sem
  dependência de AWS).
- `tests/integration/test_dynamodb_grant_status_repository.py`: testa o
  adapter DynamoDB real (incluindo a Query no GSI) usando `moto`.
- `tests/integration/test_api_check_step.py`: testa o contrato HTTP de
  `/checkStep` (200/404/422) com `TestClient`, usando um use case fake via
  `dependency_overrides` do FastAPI.

## Variáveis de ambiente

Veja [.env.example](.env.example) para a lista completa. As mais relevantes:

| Variável | Padrão | Descrição |
|---|---|---|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | Endpoint do LocalStack. Deixe vazio para AWS real. |
| `DYNAMODB_TABLE_NAME` | `sg-share-processing-records` | Tabela consultada |
| `DYNAMODB_GRANT_ID_INDEX_NAME` | `grant_id-processed_at-index` | Nome do GSI usado na Query |
