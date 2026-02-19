import pytest
from backend.database import SessionLocal, engine
from backend.models import Base, Player, WorkerPlacement
from backend.seed import seed_initial_game
from backend.game_engine import place_worker, undo_last_placement
from backend.main import get_player_availability

# Reuse fixture
@pytest.fixture
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_initial_game()
    db = SessionLocal()
    yield db
    db.close()

def test_full_usage_unavailable(db_session):
    """Verify that when all workers are placed, availability returns False."""
    player = db_session.get(Player, 1)
    # Default 3 workers.
    
    # Place 3 workers
    place_worker(db_session, player.id, 1, "raise_funds")
    place_worker(db_session, player.id, 2, "marketing")
    place_worker(db_session, player.id, 3, "play_card")
    
    report = get_player_availability(1, player.id, db_session)
    
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
    report = get_player_availability(1, player.id, db_session)
    assert report["marketing"]["available"] is False
    
    # Undo last
    undo_last_placement(db_session, player.id)
    
    # Verify available again
    report = get_player_availability(1, player.id, db_session)
    assert report["marketing"]["available"] is True

def test_projected_funds_unlock_actions(db_session):
    """Verify that projected funds from 'raise_funds' unlock actions for subsequent workers."""
    player = db_session.get(Player, 1)
    # Setup: 0 funds.
    player.corporate_funds = 0
    player.income = 5 # Enough to buy recruit tier 4 ($2)
    db_session.commit()
    
    # Verify Recruit is currently unavailable
    report = get_player_availability(1, player.id, db_session)
    assert report["recruit"]["available"] is False
    assert report["recruit"]["reason"].startswith("Insufficient Funds")
    
    # Place Worker 1 on Raise Funds
    place_worker(db_session, player.id, 1, "raise_funds")
    
    # Check availability for NEXT worker (Worker 2)
    # The endpoint calculates projected state including Worker 1's effect (raise funds -> +5 income)
    report = get_player_availability(1, player.id, db_session)
    
    # Recruit should now be available because projected funds = 0 + 5 = 5. Cost is $2.
    assert report["recruit"]["available"] is True, f"Recruit should be unlocked by projected funds. Reason: {report['recruit'].get('reason')}"
    
    # Verify worker check passed (we have 3 workers total, used 1, 2 left)
