from datetime import time
from typing import List, Dict
import pytest
from unittest.mock import MagicMock

from backend.database import SessionLocal, engine
from backend.models import Base, Player
from backend.game_engine import place_worker, validate_action_requirements
from backend.seed import seed_initial_game

@pytest.fixture
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_initial_game()
    db = SessionLocal()
    yield db
    db.close()

def test_always_available_actions(db_session):
    """
    Verify that Marketing, Raise Funds, and Play Card are available even with minimal resources.
    """
    player = db_session.get(Player, 1)
    player.corporate_funds = 0
    player.personal_funds = 0
    player.reputation = -3
    player.compute_level = 1
    player.model_version = 1
    player.net_worth_level = 0
    db_session.commit()

    res = place_worker(db_session, player_id=player.id, worker_number=1, action_type="marketing")
    assert "error" not in res, f"Marketing should be allowed. Error: {res.get('error')}"

    res = place_worker(db_session, player_id=player.id, worker_number=2, action_type="raise_funds")
    assert "error" not in res, f"Raise Funds should be allowed. Error: {res.get('error')}"

    res = place_worker(db_session, player_id=player.id, worker_number=3, action_type="play_card")
    assert "error" not in res, f"Play Card should be allowed. Error: {res.get('error')}"
    
def test_conditional_actions_fail_without_resources(db_session):
    """
    Verify that validation properly fails for cost-dependent actions when broke.
    """
    player = db_session.get(Player, 1)
    player.corporate_funds = 0
    db_session.commit()
    
    res = place_worker(db_session, player.id, 1, "buy_chips")
    assert "error" in res, "Buy Chips should fail with $0"
    
    res = place_worker(db_session, player.id, 1, "recruit")
    assert "error" in res, "Recruit should fail with $0"

def test_projected_availability_raise_funds_unlocks_net_worth(db_session):
    """
    Scenario:
    - Player Funds: $2.
    - Income: $3 (Set via power/subsidy).
    - Increase Net Worth Cost: $3. 
    - Current State: $2 < $3 (Unavailable).
    - Action 1: Raise Funds (Projected Funds becomes $3
    - Action 2: Increase Net Worth (Cost $3).
    - Checks: Action 2 should NOT fail.
    """
    player = db_session.get(Player, 1)
    player.corporate_funds = 2
    player.net_worth_level = 0 # Startup
    # Needed for Increase Net Worth:
    # Cost: $3 to get to Millionaire (1).
    # Reputation: min -3. (Default 0 is fine).
    
    # Set Income to 3 ensures Raise Funds gives +3.
    player.power = 3 
    player.subsidy_tokens = 0
    player.income = 3
    db_session.commit()
    
    # 1. Place Worker 1 on Raise Funds
    res1 = place_worker(db_session, player.id, 1, "raise_funds")
    assert "error" not in res1
    
    # 2. Place Worker 2 on Increase Net Worth
    # The backend projection logic must handle this.
    res2 = place_worker(db_session, player.id, 2, "increase_net_worth")
    
    assert "error" not in res2, f"Projected funds should allow action. Got: {res2.get('error')}"
