
import pytest
from backend.database import SessionLocal, engine
from backend.models import Base, Player
from backend.game_engine import place_worker, undo_last_placement
from backend.seed import seed_initial_game
from backend.availability import ActionValidator
from backend.main import get_player_availability

# ---------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------

@pytest.fixture
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_initial_game()
    db = SessionLocal()
    yield db
    db.close()

# ---------------------------------------------------------
# UNIT TESTS (ActionValidator)
# ---------------------------------------------------------

def test_actions_unavailable_with_zero_funds():
    """Verify that all actions requiring money are unavailable when funds are 0."""
    state = {
        "corporate_funds": 0,
        "net_worth_level": 0,
        "reputation": 0,
        "compute_level": 1,
        "model_version": 1,
        "total_workers": 3,
        "presence_count": 1,
        "presence_regions": [1] # Random start
    }
    validator = ActionValidator(state)
    report = validator.get_availability_report()

    # Free actions should be available
    assert report["raise_funds"]["available"] is True
    assert report["play_card"]["available"] is True
    assert report["marketing"]["available"] is True

    # Paid actions should be unavailable
    assert report["buy_chips"]["available"] is False
    assert report["buy_chips"]["reason"].startswith("Insufficient Funds")

    assert report["recruit"]["available"] is False
    assert report["recruit"]["reason"].startswith("Insufficient Funds")
    
    assert report["increase_net_worth"]["available"] is False
    assert report["increase_net_worth"]["reason"].startswith("Insufficient Funds")

    assert report["scale_presence"]["available"] is False
    assert report["scale_presence"]["reason"].startswith("Insufficient Funds")

def test_startup_limitations():
    """Verify Startup (Net Worth 0) cannot access advanced tiers."""
    # Give plenty of money but 0 Net Worth
    state = {
        "corporate_funds": 100,
        "net_worth_level": 0,
        "reputation": 0,
        "compute_level": 2, # Trying to go to 3
        "model_version": 2, # Trying to go to 3
        "total_workers": 4, # Trying for 5th worker
        "presence_count": 1,
        "presence_regions": [1]
    }
    validator = ActionValidator(state)
    report = validator.get_availability_report()

    # Compute Level 3 requires Millionaire (NW 1)
    assert report["buy_chips"]["available"] is False
    assert report["buy_chips"]["reason"] == "Net Worth Too Low"

    # Model Version 3 requires Millionaire (NW 1)
    assert report["train_model"]["available"] is False
    # Note: train_model validates against next version cost which includes NW check
    assert report["train_model"]["reason"] == "Net Worth Too Low"

    # Recruit 5th Worker requires Millionaire (NW 1)
    assert report["recruit"]["available"] is False
    assert report["recruit"]["reason"] == "Net Worth Too Low"

def test_reputation_blocking():
    """Verify Reputation constraints block actions."""
    # Situation: Want to increase NW to Millionaire (Cost: $3, -2 Rep)
    # Current Rep: -3. Result would be -5. Allowed floor: -3.
    state = {
        "corporate_funds": 100,
        "net_worth_level": 0,
        "reputation": -2, # -2 - 2 = -4 (< -3) -> FAIL
        "presence_regions": [1]
    }
    validator = ActionValidator(state)
    report = validator.get_availability_report()
    
    assert report["increase_net_worth"]["available"] is False
    assert report["increase_net_worth"]["reason"] == "Reputation Too Low"
    
    # Increase rep to -1. (-1 - 2 = -3) -> OK
    state["reputation"] = -1
    validator = ActionValidator(state)
    report = validator.get_availability_report()
    assert report["increase_net_worth"]["available"] is True

def test_scale_presence_adjacencies():
    """Verify Scale Presence availability based on valid targets."""
    # Case 1: Has money, adjacent options exist -> Available
    state = {
        "corporate_funds": 100,
        "presence_count": 1, 
        "presence_regions": [1], # Adjacent: 2, 6
        "net_worth_level": 0
    }
    validator = ActionValidator(state)
    report = validator.get_availability_report()
    assert report["scale_presence"]["available"] is True
    
    # Case 2: Max Presence Reached
    state["presence_count"] = 10
    validator = ActionValidator(state)
    assert validator.get_availability_report()["scale_presence"]["available"] is False
    assert validator.get_availability_report()["scale_presence"]["reason"] == "Max Presence Reached"

def test_train_model_compute_limitation():
    """Verify model cannot exceed compute level."""
    state = {
        "corporate_funds": 100,
        "net_worth_level": 2, # Billionaire, money no issue
        "compute_level": 2,
        "model_version": 2, # Next is 3
        "presence_regions": [1]
    }
    # Compute 2 < Target 3 -> Fail
    validator = ActionValidator(state)
    res = validator.can_train_model()
    assert res["available"] is False
    assert res["reason"] == "Compute Level 3 Required"
    
    # Upgrade compute -> Pass
    state["compute_level"] = 3
    validator = ActionValidator(state)
    res = validator.can_train_model()
    assert res["available"] is True

# ---------------------------------------------------------
# INTEGRATION TESTS (DB + Game Logic)
# ---------------------------------------------------------

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

def test_full_usage_unavailable(db_session):
    """Verify that when all workers are placed, availability returns False."""
    player = db_session.get(Player, 1)
    # Default 3 workers.
    
    # Place 3 workers
    place_worker(db_session, player.id, 1, "raise_funds")
    place_worker(db_session, player.id, 2, "marketing")
    place_worker(db_session, player.id, 3, "play_card")
    
    report = get_player_availability(1, player.id, db=db_session)
    
    # All actions should be unavailable
    for action, status in report.items():
        assert status["available"] is False, f"Action {action} should be unavailable when no workers left."
        assert status["reason"] == "No Workers Remaining"

def test_undo_restores_availability(db_session):
    """Verify that undoing a placement restores availability."""
    player = db_session.get(Player, 1)
    # Place 3 workers
    place_worker(db_session, player.id, 1, "raise_funds")
    place_worker(db_session, player.id, 2, "marketing")
    place_worker(db_session, player.id, 3, "play_card")
    
    # Verify exhausted
    report = get_player_availability(1, player.id, db=db_session)
    assert report["marketing"]["available"] is False
    
    # Undo last
    undo_last_placement(db_session, player.id)
    
    # Verify available again
    report = get_player_availability(1, player.id, db=db_session)
    assert report["marketing"]["available"] is True

def test_projected_funds_unlock_actions(db_session):
    """Verify that projected funds from 'raise_funds' unlock actions for subsequent workers."""
    player = db_session.get(Player, 1)
    # Setup: 0 funds.
    player.corporate_funds = 0
    player.income = 5 # Enough to buy recruit tier 4 ($2)
    db_session.commit()
    
    # Verify Recruit is currently unavailable
    report = get_player_availability(1, player.id, db=db_session)
    assert report["recruit"]["available"] is False
    assert report["recruit"]["reason"].startswith("Insufficient Funds")
    
    # Place Worker 1 on Raise Funds
    place_worker(db_session, player.id, 1, "raise_funds")
    
    # Check availability for NEXT worker (Worker 2)
    # The endpoint calculates projected state including Worker 1's effect (raise funds -> +5 income)
    report = get_player_availability(1, player.id, db=db_session)
    
    # Recruit should now be available because projected funds = 0 + 5 = 5. Cost is $2.
    assert report["recruit"]["available"] is True, f"Recruit should be unlocked by projected funds. Reason: {report['recruit'].get('reason')}"
