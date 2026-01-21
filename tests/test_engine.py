import pytest
from backend.database import SessionLocal, engine
from backend.models import (
    Base,
    Component,
    Player,
    Game,
    WorkerPlacement,
    Presence,
    RegionState, ReputationTile,
)
from backend.game_engine import (
    draw_card,
    play_card,
    execute_raise_funds_sequence,
    place_worker,
    resolve_entire_round,
    buy_chips,
    train_model,
    scale_presence,
    increase_net_worth,
    update_player_income,
    recruit_worker,
    execute_action, execute_marketing, check_reputation_tiles,
)
from backend.enums import ZoneType
from backend.seed import seed_initial_game


@pytest.fixture
def db_session():
    """Sets up a fresh database, seeds it, and provides a session."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_initial_game()

    db = SessionLocal()
    yield db  # This is what the test functions receive

    db.close()


# --- TESTS ---
def test_starting_resource_values(db_session):
    """Verifies that the seed correctly applies Disruptopia starting stats."""
    player = db_session.get(Player, 1)

    assert player.power == 3
    assert player.income == 3
    assert player.corporate_funds == 3
    assert player.personal_funds == 0
    assert player.total_workers == 3
    assert player.compute_level == 1
    assert player.model_version == 0


def test_draw_research_card(db_session):
    player_id = 1
    result = draw_card(db_session, player_id, ZoneType.RESEARCH_DECK)

    assert "error" not in result
    drawn_card_id = result["component_id"]
    updated_card = (
        db_session.query(Component).filter(Component.id == drawn_card_id).first()
    )

    assert updated_card.zone == "hand_p1"
    assert updated_card.owner_id == player_id


def test_play_effect_card(db_session):
    player_id = 1
    card_id = 1
    target_slot = 1

    card = db_session.query(Component).filter(Component.id == card_id).first()
    card.zone = f"hand_p{player_id}"
    card.owner_id = player_id
    db_session.commit()

    result = play_card(db_session, player_id, card_id, target_slot)

    expected_zone = f"active_effect_card_slot_{target_slot}_p{player_id}"
    assert card.zone == expected_zone
    assert card.owner_id == player_id


def test_multi_raise_funds(db_session):
    player = db_session.query(Player).filter(Player.id == 1).first()
    player.power = 20
    player.subsidy_tokens = 5
    player.net_worth_level = 2
    player.income = 30
    player.corporate_funds = 10
    player.personal_funds = 0
    db_session.commit()

    result = execute_raise_funds_sequence(db_session, player.id, [2, 2])

    assert player.personal_funds == 29  # 10 + 19
    assert player.corporate_funds == 19
    assert len(result["sequence_results"]) == 2


def test_resolution_turn_order(db_session):
    game = db_session.query(Game).first()
    game.p1_token_index = 2

    # Since we seed in the fixture, we might want to clear
    # players if seed_initial_game adds them, or just use them.
    # For this test, let's ensure we have exactly our 3 controlled players.
    db_session.query(Player).delete()

    players = [
        Player(user_name="Alpha", player_order=0, game_id=game.id, total_workers=3),
        Player(user_name="Bravo", player_order=1, game_id=game.id, total_workers=3),
        Player(user_name="Charlie", player_order=2, game_id=game.id, total_workers=3),
    ]
    db_session.add_all(players)
    db_session.commit()

    for p in players:
        place_worker(db_session, p.id, 1, "marketing")

    result = resolve_entire_round(db_session, game.id)

    assert result["new_p1_index"] == 0
    assert db_session.query(WorkerPlacement).count() == 0

    db_session.refresh(game)
    assert game.p1_token_index == 0


def test_compute_progression_gates(db_session):
    player = db_session.query(Player).filter(Player.id == 1).first()
    player.corporate_funds = 10
    player.compute_level = 2
    player.net_worth_level = 0  # Startup
    db_session.commit()

    # Attempt to upgrade to Level 3 as a Startup (Should Fail)
    result = buy_chips(db_session, player.id)
    assert "error" in result
    assert "Net Worth too low" in result["error"]
    assert player.compute_level == 2

    # Promote to Millionaire and try again (Should Succeed)
    player.net_worth_level = 1
    db_session.commit()

    result = buy_chips(db_session, player.id)
    assert "error" not in result
    assert player.compute_level == 3
    assert player.corporate_funds == 7  # 10 - 3


def test_train_model_logic(db_session):
    # Setup: Startup at Model 2, trying to hit Model 3
    player = db_session.query(Player).filter(Player.id == 1).first()
    player.model_version = 2
    player.compute_level = 2  # Current compute is too low for Model 3
    player.net_worth_level = 0  # Startup
    player.presence_count = 5  # Should result in 2 Power gain
    player.reputation = 0
    player.subsidy_tokens = 1
    player.power = 10
    db_session.commit()

    # 1. Test Fail: Compute Gate
    result = train_model(db_session, player.id, worker_count=2)
    assert "error" in result
    assert "Insufficient Compute" in result["error"]

    # 2. Test Fail: Net Worth Gate (Millionaire required for V3)
    player.compute_level = 3
    db_session.commit()
    result = train_model(db_session, player.id, worker_count=2)
    assert "error" in result
    assert "Net Worth too low" in result["error"]

    # 3. Test Success: Meet all requirements
    player.net_worth_level = 1  # Millionaire
    db_session.commit()

    result = train_model(db_session, player.id, worker_count=2)

    assert result["new_version"] == 3
    assert result["new_power"] == 12
    assert result["new_income"] == 13  # Assuming 1 subsidy + 12 power

    # Verify Income updated (Billionaire multiplier is 1 for Millionaire)
    # Income = Power (12) + Subsidies (assume seed default 1 * 1) = 13
    assert player.income == 12 + (player.subsidy_tokens * 1)


def test_scale_presence_and_subsidy_depletion(db_session):
    # Setup: 2 Players in a game where tokens_per_region = 1
    player_a = db_session.get(Player, 1)
    player_b = db_session.get(Player, 2)

    # Give them both starting presence in Region 1
    db_session.add(Presence(player_id=player_a.id, region_id=1))
    db_session.add(Presence(player_id=player_b.id, region_id=1))

    # Ensure Region 2 has 1 subsidy token
    reg2 = db_session.query(RegionState).filter_by(region_id=2).first()
    reg2.subsidy_tokens_remaining = 1
    db_session.commit()

    # Player A moves to Region 2 -> Claims the only token
    res_a = scale_presence(db_session, player_a.id, 2)
    assert res_a["subsidy_claimed"] is True
    assert player_a.subsidy_tokens == 1

    # Player B moves to Region 2 -> No tokens left
    res_b = scale_presence(db_session, player_b.id, 2)
    assert res_b["subsidy_claimed"] is False
    assert player_b.subsidy_tokens == 0


def test_net_worth_upgrade_and_income_boost(db_session):
    player = db_session.get(Player, 1)
    # Setup: Startup with 5 subsidy tokens and high cash
    player.net_worth_level = 0
    player.corporate_funds = 10
    player.reputation = 0
    player.subsidy_tokens = 5
    player.power = 0
    # Startup Income = 0 + (5 * 0) = 0
    update_player_income(db_session, player)
    db_session.commit()

    # Action: Become Millionaire (Costs $3, 2 Rep)
    result = increase_net_worth(db_session, player.id)

    assert "error" not in result
    assert player.net_worth_level == 1
    assert player.reputation == -2
    assert player.corporate_funds == 7

    # Millionaire Income = 0 + (5 * 1) = 5
    assert player.income == 5
    assert result["new_income"] == 5


def test_reputation_gate_on_net_worth(db_session):
    player = db_session.get(Player, 1)
    player.net_worth_level = 1  # Millionaire
    player.reputation = -2  # Low rep
    player.corporate_funds = 20
    db_session.commit()

    # Action: Try to become Billionaire (Costs 4 Rep)
    # -2 - 4 = -6, which is below the -3 floor.
    result = increase_net_worth(db_session, player.id)

    assert "error" in result
    assert "Reputation too low" in result["error"]
    assert player.net_worth_level == 1  # Still Millionaire


def test_recruit_worker_progression(db_session):
    player = db_session.get(Player, 1)
    # Starts with 3 workers, $3 Corp Funds, Net Worth 0 (Startup)

    # 1. Recruit Worker #4 (Costs $2)
    result = recruit_worker(db_session, player.id, "marketing")
    assert "error" not in result
    assert player.total_workers == 4
    assert player.corporate_funds == 1  # 3 - 2

    # 2. Try to Recruit Worker #5 (Costs $3, requires Millionaire)
    # Give the player more money first
    player.corporate_funds = 10
    db_session.commit()

    result_fail = recruit_worker(db_session, player.id, "marketing")
    assert "error" in result_fail
    assert "Millionaire" in result_fail["error"]

    # 3. Upgrade Net Worth and try again
    player.net_worth_level = 1
    db_session.commit()
    result_success = recruit_worker(db_session, player.id, "marketing")
    assert "error" not in result_success
    assert player.total_workers == 5


def test_train_model_accumulation_scenarios(db_session):
    player = db_session.get(Player, 1)

    # Common Setup
    player.compute_level = 8
    player.net_worth_level = 2  # Billionaire
    player.corporate_funds = 100

    # --- Scenario 1: Basic Linear Growth ---
    # Upgrade V1(1), V2(1), V3(2) -> Expected V3
    strategy_1 = [1, 1, 2]
    player.model_version = 0
    for count in strategy_1:
        train_model(db_session, player.id, count)
    assert player.model_version == 3

    # --- Scenario 2: Variable High-Level Growth ---
    # Start at V4.
    # V5 costs 3, V6 costs 4.
    # Strategy: [3, 4] -> Expected V6
    strategy_2 = [3, 4]
    player.model_version = 4
    for count in strategy_2:
        train_model(db_session, player.id, count)
    assert player.model_version == 6


def test_marketing_per_net_worth(db_session):
    player = db_session.get(Player, 1)

    # --- Scenario 1: Startup (NW 0) ---
    # Setup: Startup with 0 Rep, 3 Power
    player.net_worth_level = 0
    player.reputation = 0
    player.power = 3
    db_session.commit()

    execute_marketing(db_session, player.id)
    assert player.reputation == 3  # Gains 3 Rep
    assert player.power == 3  # Gains 0 Power

    # --- Scenario 2: Millionaire (NW 1) ---
    # Setup: Millionaire with 5 Rep, 10 Power
    player.net_worth_level = 1
    player.reputation = 5
    player.power = 10
    db_session.commit()

    execute_marketing(db_session, player.id)
    assert player.reputation == 6  # Gains 1 Rep
    assert player.power == 11  # Gains 1 Power

    # --- Scenario 3: Billionaire (NW 2) Caps ---
    # Setup: Billionaire near caps (9 Rep, 39 Power)
    player.net_worth_level = 2
    player.reputation = 9
    player.power = 39
    db_session.commit()

    # Marketing as Billionaire grants 0 Rep, 2 Power
    execute_marketing(db_session, player.id)
    assert player.reputation == 9  # Stays at 9 (0 gain)
    assert player.power == 40  # Capped at 40 (instead of 41)


def test_reputation_tile_stealing_and_eligibility(db_session):
    game = db_session.query(Game).first()
    player_a = db_session.get(Player, 1)
    player_b = db_session.get(Player, 2)

    # --- Scenario 1: Millionaire Eligibility ---
    # Player A is at Rep 6 but is a STARTUP. Should NOT get Level 2 tile.
    player_a.reputation = 6
    player_a.net_worth_level = 0
    db_session.commit()
    check_reputation_tiles(db_session, player_a.id)

    tile_l2 = db_session.query(ReputationTile).filter_by(level=2).first()
    assert tile_l2.owner_id is None  # Not eligible

    # Now make Player A a Millionaire
    player_a.net_worth_level = 1
    db_session.commit()
    check_reputation_tiles(db_session, player_a.id)
    assert tile_l2.owner_id == player_a.id  # Takes it!

    # --- Scenario 2: Stealing ---
    # Player B becomes a Millionaire and hits Rep 7
    player_b.net_worth_level = 1
    player_b.reputation = 7
    db_session.commit()
    check_reputation_tiles(db_session, player_b.id)

    # Refresh tile and check owner
    db_session.refresh(tile_l2)
    assert tile_l2.owner_id == player_b.id  # Player B stole it

    # --- Scenario 3: Penalty Assignment ---
    player_a.reputation = -3
    db_session.commit()
    check_reputation_tiles(db_session, player_a.id)

    penalty_tile = db_session.query(ReputationTile).filter_by(level=0, owner_id=player_a.id).first()
    assert penalty_tile is not None  # Player A is now penalized. Poor Player A.