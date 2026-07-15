from app.database import Base, engine

# Import models so they register on Base.metadata before create_all runs.
from app.models import user  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    Base.metadata.drop_all(bind=engine)