import pytest
from backend.models import Player, Component, CardDetails
from backend.game_engine import apply_card_effect


def test_nerdy_server_optimization_logic(db_session):
    player = db_session.query(Player).first()

    # Dynamically find a card that actually has the optimization slug
    card = (
        db_session.query(Component)
        .join(CardDetails)
        .filter(CardDetails.effect_slug == "nerdy_server_optimization")
        .first()
    )
    if not card:
        pytest.fail("Optimization card not found in DB")

    player.compute_level = 2
    player.net_worth_level = 0
    db_session.commit()

    result = apply_card_effect(db_session, player.id, card.id)
    assert "error" in result
    assert "Net Worth too low" in result["error"]


def test_hire_a_lobbyist_scaling(db_session):
    """Verifies Power scales correctly: Startup +1, Millionaire +2, Billionaire +3."""
    player = db_session.query(Player).first()
    card = (
        db_session.query(Component)
        .join(CardDetails)
        .filter(CardDetails.effect_slug == "hire_a_lobbyist")
        .first()
    )

    # Startup (+1)
    player.net_worth_level = 0
    player.power = 10
    db_session.commit()

    apply_card_effect(db_session, player.id, card.id)
    assert player.power == 11

    # Millionaire (+2)
    player.net_worth_level = 1
    db_session.commit()
    apply_card_effect(db_session, player.id, card.id)
    assert player.power == 13

    # Billionaire (+3)
    player.net_worth_level = 2
    db_session.commit()
    apply_card_effect(db_session, player.id, card.id)
    assert player.power == 16
