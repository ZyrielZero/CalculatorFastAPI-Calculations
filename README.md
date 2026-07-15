# FastAPI Calculator with Secure User Model

A FastAPI application combining a web calculator with a secure user model
built on SQLAlchemy, Pydantic v2, and bcrypt. The calculator exposes four
arithmetic endpoints behind a Jinja2-rendered frontend; the user layer
handles registration, credential verification, and JWT issuance as a
fully tested service layer that HTTP routes will consume in later modules.

Docker Hub: **https://hub.docker.com/r/zyrielzero/calculator-userauth**

```bash
docker pull zyrielzero/calculator-userauth:latest
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/dbname \
  -e JWT_SECRET=<at-least-32-characters> \
  zyrielzero/calculator-userauth:latest
```

## Security Model

The `User` model (`app/models/user.py`) stores a UUID primary key,
`username` and `email` with unique indexed constraints enforced at the
database level, a bcrypt `password_hash`, an `is_active` flag,
`last_login`, and a `created_at` timestamp set by the database via
`server_default=func.now()`.

Passwords are hashed with bcrypt directly (`app/security.py`) rather than
through passlib, which is unmaintained and breaks against bcrypt >= 4.1.
Inputs beyond bcrypt's 72-byte limit are rejected explicitly instead of
being silently truncated, and verification returns False on malformed
stored hashes so a corrupted row reads as a failed login rather than a 500.

`UserCreate` validates registration input: username pattern and length,
RFC-compliant email via `EmailStr`, and a password policy requiring mixed
case and at least one digit. `UserRead` never declares `password_hash`,
so the hash cannot serialize into any response. Successful authentication
returns a `Token` envelope carrying a signed JWT.

## Setup and Run (Docker Compose)

The stack runs three services: the FastAPI app, PostgreSQL 16, and pgAdmin 4.

```bash
docker compose up --build
```

| Service    | URL                   | Credentials                        |
|------------|-----------------------|------------------------------------|
| Calculator | http://localhost:8000 | -                                  |
| pgAdmin    | http://localhost:5050 | admin@example.org / admin          |
| PostgreSQL | localhost:5432        | postgres / postgres, db fastapi_db |

Inside pgAdmin, register the server with host `db` (the Compose service
name), not localhost.

`sql/module9_raw_sql.sql` contains the Module 9 raw SQL walkthrough and can
be run section by section in the pgAdmin Query Tool against `fastapi_db`.

## Running Tests Locally

Dependencies are split in two files: `requirements.txt` is the runtime
freeze the Docker image installs, and `requirements-dev.txt` adds test and
lint tooling on top. Local development installs the dev file.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
playwright install chromium
```

Integration tests require a reachable PostgreSQL database. Point
`DATABASE_URL` at one (the Compose Postgres works) and set a `JWT_SECRET`
of at least 32 characters:

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fastapi_db
export JWT_SECRET=local-dev-secret-that-is-32-chars-min
```

Then run the suites:

```bash
pytest                                              # full suite
pytest tests/unit                                   # hashing, schemas, model defaults
pytest tests/unit tests/integration --cov-fail-under=100   # the CI coverage gate
pytest tests/e2e                                    # Playwright against a live server
```

Unit tests cover the operations layer, password hashing, schema validation,
and model column definitions with no database required. Integration tests
exercise registration, uniqueness collisions, authentication, token
resolution, and the active-user gate against a real Postgres. The e2e
fixture starts the app with the same interpreter running pytest, so results
are stable locally and in CI.

## API

| Endpoint    | Method | Body               | Success           | Error                 |
|-------------|--------|--------------------|-------------------|-----------------------|
| `/add`      | POST   | `{"a": 1, "b": 2}` | `{"result": 3}`   | `400 {"error": "..."}`|
| `/subtract` | POST   | `{"a": 5, "b": 2}` | `{"result": 3}`   | `400 {"error": "..."}`|
| `/multiply` | POST   | `{"a": 2, "b": 3}` | `{"result": 6}`   | `400 {"error": "..."}`|
| `/divide`   | POST   | `{"a": 6, "b": 2}` | `{"result": 3.0}` | `400` on zero divisor |

Malformed payloads return 400 with an `error` field via a custom validation
handler. User registration and authentication live in
`app/services/user_service.py` and `app/auth/`, covered by the integration
suite; HTTP routes for them arrive in a later module.

## CI/CD Pipeline

GitHub Actions (`.github/workflows/test.yml`) runs three sequential jobs on
every push and pull request to main.

**test** spins up a PostgreSQL 16 service container, installs
`requirements-dev.txt`, and runs unit tests, the unit + integration suite
under a 100% coverage gate, and the Playwright e2e suite.

**scan** builds the Docker image and runs a Trivy vulnerability scan.
Any unpatched CRITICAL or HIGH finding fails the job, which blocks
deployment. The image installs only the runtime freeze, so test and lint
tooling never enters the scan surface.

**deploy** runs only on pushes to main after a clean scan. It builds and
pushes the image to Docker Hub tagged `latest` and with the commit SHA:
https://hub.docker.com/r/zyrielzero/calculator-userauth