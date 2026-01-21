from sqlalchemy.orm import Session
from backend.models import Player, Component
from backend.game_engine import update_player_income, check_reputation_tiles


def effect_nerdy_server_optimization(db: Session, player_id: int, card_id: int):
    """
    Research Card: +1 Compute for free.
    Requirements: Net Worth limits apply.
    """
    player = db.get(Player, player_id)
    next_level = player.compute_level + 1

    # Validation: Max Level
    if next_level > 7:
        return {"error": "Maximum compute level already reached."}

    # Validation: Net Worth Limits
    from backend.config import COMPUTE_NET_WORTH_REQ

    required_nw = COMPUTE_NET_WORTH_REQ.get(next_level, 0)
    if player.net_worth_level < required_nw:
        nw_name = "Millionaire" if required_nw == 1 else "Billionaire"
        return {
            "error": f"Net Worth too low. Upgrade to {nw_name} for this compute level."
        }

    # Execute: Free upgrade (no cost deducted)
    player.compute_level = next_level
    db.commit()

    return {
        "success": True,
        "action": "card_effect_resolved",
        "new_compute": player.compute_level,
        "message": "Server optimization complete. Compute increased.",
    }


def effect_hire_a_lobbyist(db: Session, player_id: int, card_id: int):
    """
    Influence Card: Power boost based on Net Worth.
    Startup: +1 Power. Millionaire: +2 Power. Billionaire: +3 Power.
    """
    player = db.get(Player, player_id)

    # Calculate boost based on NW level (0, 1, or 2)
    power_boost = player.net_worth_level + 1

    # Execute: Increase Power (capped at 40)
    player.power = min(40, player.power + power_boost)

    # Recalculate income since power changed
    update_player_income(db, player)
    db.commit()

    return {
        "success": True,
        "action": "card_effect_resolved",
        "new_power": player.power,
        "message": f"Lobbyist hired. Power increased by {power_boost}.",
    }


# Registry mapping Card Detail effect slugs to functions
CARD_EFFECT_REGISTRY = {
    "nerdy_server_optimization": effect_nerdy_server_optimization,
    "hire_a_lobbyist": effect_hire_a_lobbyist,
}
