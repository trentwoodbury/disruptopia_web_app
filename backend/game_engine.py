from sqlalchemy.orm import Session
from backend.models import Component, Player, CardDetails
from backend.seed import ZoneType


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


def play_card(db: Session, player_id: int, card_id: int, target_slot: int = None):
    card = db.query(Component).filter(Component.id == card_id).first()

    if not card or card.owner_id != player_id:
        return {"error": f"Player {player_id} does not own this card."}

    # Handle Effect Cards
    if card.card_details.is_effect:
        if target_slot is None:
            return {"error": "Target slot cannot be None for Effect Cards."}
        if not (1 <= target_slot <= 3):
            return {"error": "Invalid slot. Must be 1, 2, or 3."}

        target_zone = f"active_effect_card_slot_{target_slot}_p{player_id}"

        # Check if slot is occupied
        existing_occupant = db.query(Component).filter(
            Component.zone == target_zone,
            Component.game_id == card.game_id
        ).first()

        if existing_occupant:
            # Note: card.sub_type should be "research", "influence", or "sabotage"
            existing_occupant.zone = f"{existing_occupant.sub_type}_discard"
            existing_occupant.owner_id = None

        card.zone = target_zone

    # Handling for Action Cards
    else:
        if target_slot is not None:
            return {"error": "Action cards cannot be played into Effect Card slots."}
        card.zone = f"{card.sub_type}_discard"
        card.owner_id = None

    db.commit()
    return {"action": "card_played", "card_id": card.id, "new_zone": card.zone}