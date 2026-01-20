from sqlalchemy.orm import Session
from models import Component, Player
from seed import ZoneType


def draw_card(db: Session, player_id: int, deck_type: ZoneType):
    """
    Moves a card from a specific deck to a player's hand.
    """
    # 1. Find the "top" card of the requested deck
    # In a real game, you'd shuffle or pick the first one
    card = db.query(Component).filter(
        Component.zone == deck_type.value,
        Component.game_id == 1  # TODO: Hardcoded for now, will be dynamic later
    ).first()

    if not card:
        # TODO: Add handling for reshuffling the discard
        return {"error": f"No cards left in {deck_type.value}"}

    # 2. Determine the target zone based on player_id
    # This matches your ZoneType enum naming convention: hand_p1, hand_p2, etc.
    target_zone = f"hand_p{player_id}"

    # 3. Update the component state
    card.zone = target_zone
    card.owner_id = player_id
    card.is_face_up = False  # Usually cards in hand are hidden from others

    db.commit()
    db.refresh(card)

    return {
        "action": "card_drawn",
        "player_id": player_id,
        "component_id": card.id,
        "new_zone": card.zone
    }


def move_piece(db: Session, component_id: int, new_x: float, new_y: float):
    """
    Updates the physical coordinates of a piece on the board.
    """
    piece = db.query(Component).filter(Component.id == component_id).first()

    if piece:
        piece.pos_x = new_x
        piece.pos_y = new_y
        # When a piece is moved, we bump its z_index to bring it to front
        piece.z_index += 1

        db.commit()
        return {"success": True, "component_id": component_id, "x": new_x, "y": new_y}

    return {"error": "Piece not found"}