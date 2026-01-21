# tests/conftest.py
import pytest
from backend.database import SessionLocal, engine
from backend.models import Base


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
