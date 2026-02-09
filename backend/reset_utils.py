from backend.database import engine
from backend.models import Base
from backend.seed import seed_initial_game

def reset_game_state():
    """Drops all tables and re-seeds the game."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_initial_game()
    return {"status": "Game Reset"}
