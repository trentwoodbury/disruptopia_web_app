import pytest
from backend.models import Player, Component, CardDetails
from backend.game_engine import apply_card_effect


def test_nerdy_optimization_logic(db_session):
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
    db_session.commit()

    result = apply_card_effect(db_session, player.id, card.id)
    assert "success" in result
    assert player.compute_level == 3


def test_hire_a_lobbyist_scaling(db_session):
    """Verifies Power scales correctly: Startup +1, Millionaire +2, Billionaire +3."""
    player = db_session.query(Player).first()

    # Create dummy card
    details = CardDetails(name="dummy", is_effect=False, qty="1", cost=1, deck="influence", effect_slug="hire_lobbyist")
    db_session.add(details)
    db_session.flush()
    card = Component(name="dummy_1", comp_type="card", sub_type="influence", zone="play", game_id=player.game_id, card_details_id=details.id)
    db_session.add(card)
    db_session.commit()

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

def test_play_card_placement(db_session):
    """Verifies that placing a worker on play_card saves the target_card_id."""
    from backend import game_engine
    player = db_session.query(Player).first()
    
    # Needs a dummy card in hand
    details = CardDetails(name="dummy_action", is_effect=False, qty="1", cost=1, deck="influence", effect_slug="dummy")
    db_session.add(details)
    db_session.flush()
    card = Component(name="dummy_action_1", comp_type="card", sub_type="influence", zone=f"hand_p{player.id}", owner_id=player.id, game_id=player.game_id, card_details_id=details.id)
    db_session.add(card)
    
    # Need to make sure the player has enough workers, let's bump the total workers so they can place
    player.total_workers = 5
    db_session.commit()

    # Place a worker to play the card
    result = game_engine.place_worker(db_session, player.id, worker_number=1, action_type="play_card", target_region=None, target_card_id=card.id)
    assert result["action"] == "worker_placed"
    
    # Verify it was saved in the database
    from backend.models import WorkerPlacement
    placement = db_session.query(WorkerPlacement).filter_by(player_id=player.id, action_type="play_card").first()
    assert placement is not None
    assert placement.target_card_id == card.id

def test_hand_limit_discard(db_session):
    """Verifies that drawing over the limit triggers discard requirements."""
    from backend import game_engine
    from backend.seed import ZoneType
    player = db_session.query(Player).first()

    # Add 6 cards to hand so we're starting over the limit
    for i in range(5):
        details = CardDetails(name=f"dummy_{i}", is_effect=False, qty="1", cost=1, deck="influence", effect_slug="dummy")
        db_session.add(details)
        db_session.flush()
        card = Component(name=f"dummy_{i}_1", comp_type="card", sub_type="influence", zone=f"hand_p{player.id}", owner_id=player.id, game_id=player.game_id, card_details_id=details.id)
        db_session.add(card)
    
    # 5 cards in hand exactly. Let's draw another.
    db_session.commit()

    # We don't need to manually inject a card because the deck is full from seed_initial_game()
    db_session.commit()

    res = game_engine.execute_round_start_draw(db_session, player.id)
    assert res.get("status") == "must_discard"
    
    # We should have 3 draw results. Pick the first one.
    drawn_card_id = res["results"][0]["component_id"]
    
    # Discard the card we just drew
    discard_res = game_engine.discard_card(db_session, player.id, drawn_card_id)
    assert "error" not in discard_res
    
    # Verify the discarded card
    card = db_session.get(Component, drawn_card_id)
    assert "discard" in card.zone
    assert card.owner_id is None

def test_initial_hand_distribution(db_session):
    """Verifies that players start with 3 cards after seed_initial_game."""
    # The db_session fixture already calls seed_initial_game() for a fresh state
    
    players = db_session.query(Player).order_by(Player.id).all()
    # P1 and P2 should each have exactly 3 cards
    for p in players:
        hand = db_session.query(Component).filter_by(owner_id=p.id).all()
        # Verify 3 cards exactly
        assert len(hand) == 3
        # Verify 1 from each deck
        decks = [card.sub_type for card in hand]
        assert "research" in decks
        assert "influence" in decks
        assert "sabotage" in decks
        
        # Verify image names are not missing 
        for card in hand:
            assert card.card_details.image_file is not None
            assert card.card_details.image_file.endswith(".png")

def test_resolve_play_card_discard(db_session):
    """Verifies that cards are actually discarded when played through resolve_entire_round."""
    from backend import game_engine
    player = db_session.query(Player).first()

    # Needs a dummy card in hand
    details = CardDetails(name="dummy_action", is_effect=False, qty="1", cost=1, deck="influence", effect_slug="dummy_sabotage")
    db_session.add(details)
    db_session.flush()
    card = Component(name="dummy_action_1", comp_type="card", sub_type="influence", zone=f"hand_p{player.id}", owner_id=player.id, game_id=player.game_id, card_details_id=details.id)
    db_session.add(card)
    db_session.flush()
    
    # Must also register dummy effect for it to pass apply_card_effect validation!
    from backend.card_effects import CARD_EFFECT_REGISTRY
    CARD_EFFECT_REGISTRY["dummy_sabotage"] = lambda db, p_id, c_id: {"success": True, "message": "Dummy effect completed"}

    place_res = game_engine.place_worker(db_session, player.id, worker_number=1, action_type="play_card", target_region=None, target_card_id=card.id)
    assert "error" not in place_res
    
    # We must explicitly set target_card_id because the test doesn't simulate full frontend request
    db_session.commit()
    
    # Resolve the round
    res = game_engine.resolve_entire_round(db_session, player.game_id)
    assert res["action"] == "round_resolved"
    
    # To check what happened to the card, let's query the db directly before asserting.
    db_session.refresh(card)
    assert card.zone == "influence_discard", f"Card zone is {card.zone}. Play card result: {res}"

    # Verify the card is no longer in the player's hand, but in the discard pile
    db_session.refresh(card)
    assert card.zone == "influence_discard"
    assert card.owner_id is None

def test_finish_round_draws_cards(db_session):
    """Verifies that main.py finish_round correctly triggers execute_round_start_draw."""
    from backend import main
    from backend.models import Player, Component
    
    player = db_session.query(Player).first()
    
    # Empty hand first
    db_session.query(Component).filter(Component.zone == f"hand_p{player.id}").delete()
    db_session.commit()
    
    # Verify hand is empty
    assert db_session.query(Component).filter(Component.zone == f"hand_p{player.id}").count() == 0
    
    # Call finish round logic directly
    res = main.finish_round(player.game_id, db_session)
    assert res["status"] == "round_finished"
    
    # Hand should now have 3 cards (1 from each deck)
    hand = db_session.query(Component).filter(Component.zone == f"hand_p{player.id}").all()
    assert len(hand) == 3
