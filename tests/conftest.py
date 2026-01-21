# tests/conftest.py
import pytest
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.seed import seed_initial_game


@pytest.fixture(scope="function")
def db_session():
    """
    Sets up a fresh database schema and seeds initial data before every test.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Seed the initial data (Players, Cards, Regions, Tiles)
    # This must run before the session is opened so the session sees the data.
    seed_initial_game()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        # to keep the DB file small
        Base.metadata.drop_all(bind=engine)
