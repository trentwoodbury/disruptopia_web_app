# tests/conftest.py
import pytest
from backend.database import SessionLocal, engine
from backend.models import Base
from backend.seed import seed_initial_game


from backend.main import app, get_db


@pytest.fixture(scope="function")
def db_session():
    """
    Sets up a fresh database schema and seeds initial data before every test.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Seed the initial data (Players, Cards, Regions, Tiles)
    seed_initial_game()
    session = SessionLocal()
    
    # Override get_db to use this session
    def override_get_db():
        try:
            yield session
        finally:
            pass # Session is closed by the fixture
            
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        # We no longer drop tables here so that the post-test DB state persists
