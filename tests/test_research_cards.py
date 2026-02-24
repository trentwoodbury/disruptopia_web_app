
import pytest
from backend.database import SessionLocal, engine
from backend.models import Base, Player, Component, CardDetails
from backend.seed import seed_initial_game
from backend.seed_research_cards import seed_research_cards
from backend.game_engine import play_card, place_worker, resolve_entire_round, execute_train_model, execute_buy_chips, draw_card
from backend.enums import ZoneType, CardCategory

@pytest.fixture
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_initial_game()
    db = SessionLocal()
    seed_research_cards(db, 1) # Ensure cards exist
    yield db
    db.close()

def _get_card_by_slug(db, slug):
    details = db.query(CardDetails).filter_by(effect_slug=slug).first()
    return db.query(Component).filter_by(card_details_id=details.id).first()

def test_gpu_tech_modifier(db_session):
    """Test GPU Tech reduces model cost."""
    player = db_session.get(Player, 1)
    # Give player resources
    player.total_workers = 5
    player.compute_level = 5
    player.net_worth_level = 2
    db_session.commit()
    
    card = _get_card_by_slug(db_session, "gpu_tech")
    card.owner_id = player.id
    card.zone = f"hand_p{player.id}"
    db_session.commit()

    # Play card (Cost 1)
    place_worker(db_session, player.id, 1, "play_card")
    res = play_card(db_session, player.id, card.id, target_slot=None)
    assert res["action"] == "card_played"
    assert player.temp_model_cost_worker_reduction == 1
    
    # Train Model (Cost normally 1 or 2 depending on level)
    # Level 0->1 costs 1 worker. GPU Tech reduces by 1 -> Cost 0? (Min 1 usually?)
    # Implementation: max(1, base - reduction)
    # Let's check level 4->5 (Base 3). GPU Tech -> 2.
    player.model_version = 4
    db_session.commit()
    
    # Execute with 2 workers (should succeed if cost reduced from 3 to 2)
    # Wait, execute_train_model expects `worker_count`.
    res = execute_train_model(db_session, player.id, worker_count=2)
    assert "error" not in res
    assert res["new_version"] == 5

def test_microdosing_interns(db_session):
    """Test Microdosing reduces card play cost."""
    player = db_session.get(Player, 1)
    # Play Microdosing (Cost 0)
    card = _get_card_by_slug(db_session, "microdosing_interns")
    card.owner_id = player.id
    card.zone = f"hand_p{player.id}"
    db_session.commit()
    
    place_worker(db_session, player.id, 1, "play_card") # Capacity 1
    res = play_card(db_session, player.id, card.id)
    assert res["action"] == "card_played"
    assert player.temp_card_cost_worker_reduction == 1
    
    # Now try to play Cost 1 card (e.g. GPU Tech)
    # Capacity used: card.cost=0.
    # GPU Tech Cost=1. Reduced by 1 -> 0.
    # Total Spent: 0 + 0 = 0. Capacity: 1. OK.
    
    card2 = _get_card_by_slug(db_session, "gpu_tech")
    card2.owner_id = player.id
    card2.zone = f"hand_p{player.id}"
    db_session.commit()
    
    res = play_card(db_session, player.id, card2.id)
    assert res["action"] == "card_played"
    assert player.workers_spent_on_cards == 0 # Both cost 0 effectively.

def test_big_compute_energy(db_session):
    """Test Big Compute Energy bonus."""
    player = db_session.get(Player, 1)
    card = _get_card_by_slug(db_session, "big_compute_energy")
    card.owner_id = player.id
    card.zone = f"hand_p{player.id}"
    db_session.commit()
    
    place_worker(db_session, player.id, 1, "play_card")
    res = play_card(db_session, player.id, card.id, target_slot=1)
    assert res["action"] == "card_played"
    assert player.temp_compute_gain_power_bonus == 2
    
    # Upgrade Compute
    old_pwr = player.power
    player.corporate_funds = 10
    execute_buy_chips(db_session, player.id)
    
    assert player.power == old_pwr + 2

def test_hackathon_discount(db_session):
    """Test Hackathon compute discount."""
    player = db_session.get(Player, 1)
    card = _get_card_by_slug(db_session, "hackathon")
    card.owner_id = player.id
    card.zone = f"hand_p{player.id}"
    player.corporate_funds = 10 
    player.total_workers = 5
    db_session.commit()
    
    place_worker(db_session, player.id, 1, "play_card")
    place_worker(db_session, player.id, 2, "play_card") # Hackathon costs 2
    res = play_card(db_session, player.id, card.id)
    assert res.get("action") == "card_played", f"Failed to play card: {res}"
    assert player.temp_compute_monetary_discount == 3
    
    # Upgrade Compute (Level 1->2 Cost 2?)
    # Cost table: 2->2, 3->3...
    # Start Level 1. Upgrade to 2. Cost 2.
    # Discount 3. Final Cost 0.
    old_funds = player.corporate_funds
    execute_buy_chips(db_session, player.id)
    assert player.corporate_funds == old_funds # No cost paid
    assert player.compute_level == 2

def test_unethical_data(db_session):
    """Test Drawing 2 cards logic."""
    player = db_session.get(Player, 1)
    card = _get_card_by_slug(db_session, "unethical_data")
    card.owner_id = player.id
    card.zone = f"hand_p{player.id}"
    db_session.commit()
    
    # Move all research cards to discard to clear deck
    all_research = db_session.query(Component).filter(Component.sub_type == CardCategory.RESEARCH.value).all()
    for c in all_research:
        c.zone = "research_discard"
        c.owner_id = None
    db_session.commit()
    
    # Put a specific target card in deck (GPU Tech)
    target_card = _get_card_by_slug(db_session, "gpu_tech")
    target_card.zone = ZoneType.RESEARCH_DECK.value
    target_card.owner_id = None
    
    # Put Unethical Data in hand
    card = _get_card_by_slug(db_session, "unethical_data")
    card.owner_id = player.id
    card.zone = f"hand_p{player.id}"
    db_session.commit()
    
    place_worker(db_session, player.id, 1, "play_card")
    res = play_card(db_session, player.id, card.id)
    
    # Check that GPU Tech was played
    # GPU Tech effect adds 1 to temp_model_cost_worker_reduction
    assert player.temp_model_cost_worker_reduction == 1
    assert "Played" in res["message"]
