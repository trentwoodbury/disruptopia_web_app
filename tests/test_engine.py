import sys
import os

# Add the project root to sys.path so we can import from 'backend'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import SessionLocal
from backend.models import Component
from backend.game_engine import draw_card
from backend.seed import ZoneType


def test_draw_research_card():
    db = SessionLocal()
    try:
        # 1. Draw Card into player 1's hand.
        card_id = 2  # 'unethical_data_source' card in the research deck
        player_id = 1

        print(f"Testing: Player {player_id} drawing Research Card...")

        # 2. do the actual engine function
        result = draw_card(db, player_id, ZoneType.RESEARCH_DECK)

        # 3. Validation
        if "error" in result:
            print(f"Test Failed: {result['error']}")
            return

        # 4. Query the DB to see if the change persisted
        updated_card = db.query(Component).filter(Component.id == card_id).first()

        assert updated_card.zone == "hand_p1"
        assert updated_card.owner_id == player_id

        print("Success!")
        print(f"Card '{updated_card.name}' moved to {updated_card.zone}.")
        print(f"Broadcast Result: {result}")

    finally:
        db.close()


if __name__ == "__main__":
    test_draw_research_card()