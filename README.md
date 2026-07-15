# FastAPI Calculator — Calculation Modeling

A FastAPI application pairing a web calculator with a secure user layer,
built on SQLAlchemy 2.0, Pydantic v2, and bcrypt. Four arithmetic
endpoints sit behind a Jinja2-rendered frontend; registration, credential
verification, and JWT issuance run as a fully tested service layer. This
repository carries that foundation forward into data modeling: a
Calculation model with schema validation and a factory-driven operation
layer, with BREAD routes to follow.

Docker Hub: **<https://hub.docker.com/r/zyrielzero/calculator-calculations>**

```
docker pull zyrielzero/calculator-calculations:latest
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/dbname \
  -e JWT_SECRET=<at-least-32-characters> \
  zyrielzero/calculator-calculations:latest
```

## Security Model

The `User` model (`app/models/user.py`) stores a UUID primary key,
`username` and `email` under unique indexed constraints enforced at the
database level, a bcrypt `password_hash`, an `is_active` flag,
`last_login`, and a `created_at` timestamp stamped by the database
through `server_default=func.now()`.

Passwords are hashed with bcrypt directly (`app/security.py`) rather than
through passlib, which is unmaintained and breaks against bcrypt >= 4.1.
Inputs beyond bcrypt's 72-byte limit are rejected explicitly instead of
silently truncated, and verification returns False on a malformed stored
hash, so a corrupted row reads as a failed login rather than a 500.

`UserCreate` validates registration input: username pattern and length,
RFC-compliant email via `EmailStr`, and a password policy requiring mixed
case and at least one digit. `UserRead` never declares `password_hash`,
so the hash cannot serialize into any response. Successful authentication
returns a `Token` envelope carrying a signed JWT.

## Calculation Model (Module 11)

`app/models/calculation.py` stores one calculation per row: a UUID primary
key, float operands `a` and `b`, a `type` string, a `user_id` foreign key
into `users` with `ON DELETE CASCADE`, and a database-stamped `created_at`.
The result is not stored — it is computed on demand through a strategy
factory (`app/calculation_factory.py`) that resolves each type to a
registered operation class, so a stored result can never drift from its
operands. Adding a new operation is one class and one decorator.

Two CHECK constraints back the application-layer rules at the database
level: `type` must be one of `add`, `sub`, `multiply`, `divide`, and a
`divide` row can never hold a zero divisor.

`CalculationCreate` validates inbound payloads — finite numeric operands
(NaN and infinity rejected), case-insensitive type strings validated
against the enum, and a zero divisor refused on divide. `CalculationRead`
serializes the row plus the computed `result` and never exposes anything
beyond its declared fields.

Calculation tests run inside the same suites and gates as the user tests;
no workflow changes were needed:

```
pytest tests/unit/test_calculation_factory.py \
       tests/unit/test_calculation_model.py \
       tests/unit/test_calculation_schemas.py
pytest tests/integration/test_calculation_persistence.py
```

Endpoints for calculations (BREAD routes) arrive in Module 12.

## Setup and Run (Docker Compose)

The stack runs three services: the FastAPI app, PostgreSQL 16, and
pgAdmin 4.

```
docker compose up --build
```

| Service    | URL                     | Credentials                         |
| ---------- | ----------------------- | ----------------------------------- |
| Calculator | <http://localhost:8000> | -                                   |
| pgAdmin    | <http://localhost:5050> | <admin@example.org> / admin         |
| PostgreSQL | localhost:5432          | postgres / postgres, db fastapi_db  |

Inside pgAdmin, register the server with host `db` (the Compose service
name), not localhost.

## Running Tests Locally

Dependencies are split across two files: `requirements.txt` is the
runtime freeze the Docker image installs, and `requirements-dev.txt`
layers test and lint tooling on top. Local development installs the dev
file.

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
playwright install chromium
```

Integration tests need a reachable PostgreSQL database. Point
`DATABASE_URL` at one (the Compose Postgres works) and set a
`JWT_SECRET` of at least 32 characters:

```
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fastapi_db
export JWT_SECRET=local-dev-secret-that-is-32-chars-min
```

Then run the suites:

```
pytest                                                     # full suite
pytest tests/unit                                          # no database required
pytest tests/unit tests/integration --cov-fail-under=100   # the CI coverage gate
pytest tests/e2e                                           # Playwright against a live server
```

Unit tests cover the operations layer, password hashing, schema
validation, and model column definitions with no database. Integration
tests exercise registration, uniqueness collisions, authentication,
token resolution, and the active-user gate against a real Postgres. The
e2e fixture starts the app with the same interpreter running pytest, so
results are stable locally and in CI.

## API

| Endpoint    | Method | Body               | Success           | Error                  |
| ----------- | ------ | ------------------ | ----------------- | ---------------------- |
| `/add`      | POST   | `{"a": 1, "b": 2}` | `{"result": 3}`   | `400 {"error": "..."}` |
| `/subtract` | POST   | `{"a": 5, "b": 2}` | `{"result": 3}`   | `400 {"error": "..."}` |
| `/multiply` | POST   | `{"a": 2, "b": 3}` | `{"result": 6}`   | `400 {"error": "..."}` |
| `/divide`   | POST   | `{"a": 6, "b": 2}` | `{"result": 3.0}` | `400` on zero divisor  |

Malformed payloads return 400 with an `error` field through a custom
validation handler. User registration and authentication live in
`app/services/user_service.py` and `app/auth/`, covered by the
integration suite; HTTP routes for them arrive in a later module.

## CI/CD Pipeline

GitHub Actions (`.github/workflows/test.yml`) runs three sequential jobs
on every push and pull request to main.

**test** spins up a PostgreSQL 16 service container, installs
`requirements-dev.txt`, and runs unit tests, the unit + integration
suite under a 100% coverage gate, and the Playwright e2e suite.

**scan** builds the Docker image and runs a Trivy vulnerability scan.
Any unpatched CRITICAL or HIGH finding fails the job, which blocks
deployment. The image installs only the runtime freeze, so test and lint
tooling never enters the scan surface.

**deploy** runs only on pushes to main after a clean scan. It builds and
pushes the image to Docker Hub tagged `latest` and with the commit SHA:
<https://hub.docker.com/r/zyrielzero/calculator-calculations>
