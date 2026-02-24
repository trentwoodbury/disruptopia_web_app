
import pytest
from backend.database import SessionLocal, engine
from backend.models import Base, Player, Component, CardDetails
from backend.seed import seed_initial_game
from backend.seed_cards import seed_influence_cards
from backend.game_engine import play_card, place_worker, draw_card, discard_card, resolve_entire_round
from backend.enums import ZoneType

@pytest.fixture
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_initial_game()
    db = SessionLocal()
    seed_influence_cards(db, 1) # Ensure cards exist
    yield db
    db.close()

def _get_card_by_slug(db, slug):
    details = db.query(CardDetails).filter_by(effect_slug=slug).first()
    return db.query(Component).filter_by(card_details_id=details.id).first()

def test_play_card_cost_logic(db_session):
    """Verify paying for cards with workers."""
    player = db_session.get(Player, 1)
    
    # 1. Get a Cost 1 card (e.g. Build HQ)
    card = _get_card_by_slug(db_session, "build_hq")
    card.zone = f"hand_p{player.id}"
    card.owner_id = player.id
    db_session.commit()
    
    # 2. Try to play with NO workers on 'play_card' -> Fail
    res = play_card(db_session, player.id, card.id, target_slot=1)
    assert "error" in res
    assert "Insufficient 'Play Card' workers" in res["error"]
    
    # 3. Place 1 worker on 'play_card'
    place_worker(db_session, player.id, 1, "play_card")
    
    # 4. Try again (Fail: Requirements for HQ is 2 Regions, we have 1)
    # Let's use a card with NO requirements but Cost 1. E.g. "Influencer Marketing"
    card_easy = _get_card_by_slug(db_session, "influencer_marketing")
    card_easy.zone = f"hand_p{player.id}"
    card_easy.owner_id = player.id
    db_session.commit()
    
    res = play_card(db_session, player.id, card_easy.id, target_slot=1)
    assert res["action"] == "card_played"
    assert player.workers_spent_on_cards == 1
    
    # 5. Try to play ANOTHER Cost 1 card (Capacity used) -> Fail
    res = play_card(db_session, player.id, card.id, target_slot=2) # Using card which failed reqs earlier? No, check cost first.
    # Actually `play_card` checks cost first.
    assert "error" in res
    assert "Insufficient" in res["error"] # Should perform Cost check before Reqs? 
    # My implementation checks Ownership -> Cost -> Logic (Reqs inside Effect).
    # So yes, logic is sound.

def test_effect_build_hq(db_session):
    player = db_session.get(Player, 1)
    player.presence_count = 2 # Meet Req
    db_session.commit()
    
    # Mock placement capacity
    place_worker(db_session, player.id, 1, "play_card")
    
    card = _get_card_by_slug(db_session, "build_hq")
    card.zone = f"hand_p{player.id}"
    card.owner_id = player.id
    db_session.commit()
    
    old_rep = player.reputation
    old_pwr = player.power
    
    res = play_card(db_session, player.id, card.id, target_slot=1)
    assert res["action"] == "card_played"
    
    assert player.reputation == old_rep + 2
    assert player.power == old_pwr + 2

def test_effect_corporate_espionage(db_session):
    player = db_session.get(Player, 1)
    player.model_version = 3 # Meet Req
    db_session.commit()
    # Cost 0
    
    card = _get_card_by_slug(db_session, "corporate_espionage")
    card.zone = f"hand_p{player.id}"
    card.owner_id = player.id
    db_session.commit()
    
    res = play_card(db_session, player.id, card.id, target_slot=1)
    with open("debug_res.txt", "w") as f:
        f.write(str(res))
    assert res["action"] == "card_played"
    # Effect is passive, just check it landed in slot
    assert card.zone == f"active_effect_card_slot_1_p{player.id}"
    
def test_reset_spent_workers(db_session):
    player = db_session.get(Player, 1)
    player.workers_spent_on_cards = 2
    db_session.commit()
    
    resolve_entire_round(db_session, 1)
    
    assert player.workers_spent_on_cards == 0
