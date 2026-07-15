import pytest
from sqlalchemy import text

from app.database import Base, SessionLocal, engine
import app.models  # noqa: F401  — register models on Base.metadata


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _clean_users(db):
    db.execute(text("TRUNCATE TABLE users"))
    db.commit()
    yield