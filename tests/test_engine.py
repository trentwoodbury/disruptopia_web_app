import pytest
from backend.database import SessionLocal, engine
from backend.models import Base, Component
from backend.game_engine import draw_card, play_card
from backend.enums import ZoneType
from backend.seed import seed_initial_game


@pytest.fixture(autouse=True)
def setup_database():
    """This runs before EVERY test function."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_initial_game()
    yield  # This is where the test happens
    # Optional: cleanup after test


def test_draw_research_card():
    db = SessionLocal()
    try:
        player_id = 1
        result = draw_card(db, player_id, ZoneType.RESEARCH_DECK)
        assert "error" not in result
        drawn_card_id = result["component_id"]
        updated_card = db.query(Component).filter(Component.id == drawn_card_id).first()

        assert updated_card.zone == "hand_p1"
        assert updated_card.owner_id == player_id
    finally:
        db.close()


def test_play_effect_card():
    db = SessionLocal()
    try:
        player_id = 1
        card_id = 1
        target_slot = 1

        # Setup state
        card = db.query(Component).filter(Component.id == card_id).first()
        card.zone = f"hand_p{player_id}"
        card.owner_id = player_id
        db.commit()

        # Execute
        result = play_card(db, player_id, card_id, target_slot)

        # Validation
        expected_zone = f"active_effect_card_slot_{target_slot}_p{player_id}"

        # Pytest will show a beautiful diff if this fails!
        assert card.zone == expected_zone
        assert card.owner_id == player_id
    finally:
        db.close()