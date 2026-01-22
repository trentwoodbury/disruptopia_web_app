import pytest
from backend.database import SessionLocal, engine
from backend.models import (
    Base,
    Component,
    Player,
    Game,
    WorkerPlacement,
    Presence,
    RegionState,
    ReputationTile,
)

# Updated imports to match new execute_ prefix and helper signatures
from backend.game_engine import (
    draw_card,
    play_card,
    execute_raise_funds_sequence,
    place_worker,
    resolve_entire_round,
    execute_buy_chips,
    execute_train_model,
    execute_scale_presence,
    execute_increase_net_worth,
    update_player_income,
    execute_recruit_worker,
    execute_marketing,
    check_reputation_tiles,
    calculate_game_leaderboard,
)
from backend.seed import ZoneType, seed_initial_game


@pytest.fixture
def db_session():
    """Sets up a fresh database, seeds it, and provides a session."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_initial_game()

    db = SessionLocal()
    yield db
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
    drawn_card_id = result["component_id"]  # Returned as requested in refactor
    updated_card = (
        db_session.query(Component).filter(Component.id == drawn_card_id).first()
    )

    assert updated_card.zone == "hand_p1"
    assert updated_card.owner_id == player_id


def test_play_effect_card(db_session):
    player_id = 1
    card_id = 1
    target_slot = 1

    card = db_session.get(Component, card_id)
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

    # Uses the updated sequence function
    result = execute_raise_funds_sequence(db_session, player.id, [2, 2])

    assert player.personal_funds == 29  # 10 + 19
    assert player.corporate_funds == 19
    assert len(result["sequence"]) == 2


def test_resolution_turn_order(db_session):
    game = db_session.query(Game).first()
    game.p1_token_index = 2

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


def test_compute_progression_gates(db_session):
    player = db_session.query(Player).filter(Player.id == 1).first()
    player.corporate_funds = 10
    player.compute_level = 2
    player.net_worth_level = 0
    db_session.commit()

    # Attempt to upgrade to Level 3 as a Startup (Should Fail)
    result = execute_buy_chips(db_session, player.id)
    assert "error" in result
    assert "Net Worth too low" in result["error"]

    player.net_worth_level = 1
    db_session.commit()

    result = execute_buy_chips(db_session, player.id)
    assert "error" not in result
    assert player.compute_level == 3
    assert player.corporate_funds == 7


def test_train_model_logic(db_session):
    player = db_session.query(Player).filter(Player.id == 1).first()
    player.model_version = 2
    player.compute_level = 2
    player.net_worth_level = 0
    player.presence_count = 5
    player.reputation = 0
    player.subsidy_tokens = 1
    player.power = 10
    db_session.commit()

    # Providing correct worker count to hit compute gate
    result = execute_train_model(db_session, player.id, worker_count=2)
    assert "error" in result
    assert "Insufficient Compute" in result["error"]

    player.compute_level = 3
    db_session.commit()
    result = execute_train_model(db_session, player.id, worker_count=2)
    assert "error" in result
    assert "Net Worth too low" in result["error"]

    player.net_worth_level = 1
    db_session.commit()

    result = execute_train_model(db_session, player.id, worker_count=2)

    assert result["new_version"] == 3
    assert result["new_power"] == 12
    assert player.income == 12 + (player.subsidy_tokens * 1)


def test_scale_presence_and_subsidy_depletion(db_session):
    player_a = db_session.get(Player, 1)
    player_b = db_session.get(Player, 2)

    db_session.add(Presence(player_id=player_a.id, region_id=1))
    db_session.add(Presence(player_id=player_b.id, region_id=1))

    reg2 = db_session.query(RegionState).filter_by(region_id=2).first()
    reg2.subsidy_tokens_remaining = 1
    db_session.commit()

    res_a = execute_scale_presence(db_session, player_a.id, 2)
    assert res_a["action"] == "presence_scaled"
    assert player_a.subsidy_tokens == 1

    res_b = execute_scale_presence(db_session, player_b.id, 2)
    assert "error" in res_b or player_b.subsidy_tokens == 0


def test_net_worth_upgrade_and_income_boost(db_session):
    player = db_session.get(Player, 1)
    player.net_worth_level = 0
    player.corporate_funds = 10
    player.reputation = 0
    player.subsidy_tokens = 5
    player.power = 0
    # Requires session for modifiers
    update_player_income(db_session, player)
    db_session.commit()

    result = execute_increase_net_worth(db_session, player.id)

    assert "error" not in result
    assert player.net_worth_level == 1
    assert player.reputation == -2
    assert player.income == 5


def test_reputation_gate_on_net_worth(db_session):
    player = db_session.get(Player, 1)
    player.net_worth_level = 1
    player.reputation = -2
    player.corporate_funds = 20
    db_session.commit()

    result = execute_increase_net_worth(db_session, player.id)

    assert "error" in result
    assert "Reputation too low" in result["error"]


def test_recruit_worker_progression(db_session):
    player = db_session.get(Player, 1)

    result = execute_recruit_worker(db_session, player.id, "marketing")
    assert "error" not in result
    assert player.total_workers == 4

    player.corporate_funds = 10
    db_session.commit()

    result_fail = execute_recruit_worker(db_session, player.id, "marketing")
    assert "error" in result_fail

    player.net_worth_level = 1
    db_session.commit()
    result_success = execute_recruit_worker(db_session, player.id, "marketing")
    assert "error" not in result_success
    assert player.total_workers == 5


def test_train_model_accumulation_scenarios(db_session):
    player = db_session.get(Player, 1)
    player.compute_level = 8
    player.net_worth_level = 2
    player.corporate_funds = 100

    strategy_1 = [1, 1, 2]
    player.model_version = 0
    for count in strategy_1:
        execute_train_model(db_session, player.id, count)
    assert player.model_version == 3

    strategy_2 = [3, 4]
    player.model_version = 4
    for count in strategy_2:
        execute_train_model(db_session, player.id, count)
    assert player.model_version == 6


def test_marketing_per_net_worth(db_session):
    player = db_session.get(Player, 1)

    player.net_worth_level = 0
    player.reputation = 0
    player.power = 3
    db_session.commit()

    execute_marketing(db_session, player.id)
    assert player.reputation == 3

    player.net_worth_level = 1
    player.reputation = 5
    player.power = 10
    db_session.commit()

    execute_marketing(db_session, player.id)
    assert player.reputation == 6
    assert player.power == 11


def test_reputation_tile_stealing_and_eligibility(db_session):
    player_a = db_session.get(Player, 1)
    player_b = db_session.get(Player, 2)

    player_a.reputation = 6
    player_a.net_worth_level = 0
    db_session.commit()
    check_reputation_tiles(db_session, player_a.id)

    tile_l2 = db_session.query(ReputationTile).filter_by(level=2).first()
    assert tile_l2.owner_id is None

    player_a.net_worth_level = 1
    db_session.commit()
    check_reputation_tiles(db_session, player_a.id)
    assert tile_l2.owner_id == player_a.id

    player_b.net_worth_level = 1
    player_b.reputation = 7
    db_session.commit()
    check_reputation_tiles(db_session, player_b.id)

    db_session.refresh(tile_l2)
    assert tile_l2.owner_id == player_b.id

    player_a.reputation = -3
    db_session.commit()
    check_reputation_tiles(db_session, player_a.id)

    penalty_tile = (
        db_session.query(ReputationTile)
        .filter_by(level=0, owner_id=player_a.id)
        .first()
    )
    assert penalty_tile is not None


def test_vp_calculation_and_funds_ranking(db_session):
    """Verifies that the 3-player fund bonus and Net Worth race VP work correctly."""
    game = db_session.query(Game).first()

    # 1. Setup 3 Players with different funds
    # Player 1: Most funds ($50), 1st Millionaire (2VP)
    p1 = db_session.get(Player, 1)
    p1.personal_funds = 50
    p1.vp = 2  # Manually simulate being 1st to Millionaire

    # Player 2: Second funds ($30), 2nd Millionaire (1VP)
    p2 = db_session.get(Player, 2)
    p2.personal_funds = 30
    p2.vp = 1

    # Player 3: Least funds ($10)
    p3 = Player(user_name="Charlie", game_id=game.id, player_order=2, personal_funds=10)
    db_session.add(p3)
    db_session.commit()

    # 2. Run the leaderboard calculation
    leaderboard = calculate_game_leaderboard(db_session, game.id)

    # Map results by player ID for easy checking
    scores = {res["player_id"]: res for res in leaderboard}

    # 3. Assertions
    # Player 1 (1st in funds): Race(2) + Funds(3) + Model/Presence (approx 1+1)
    assert scores[p1.id]["breakdown"]["funds_bonus"] == 3
    assert scores[p1.id]["breakdown"]["race_bonuses"] == 2

    # Player 2 (2nd in funds): Race(1) + Funds(1)
    assert scores[p2.id]["breakdown"]["funds_bonus"] == 1

    # Player 3 (3rd in funds): Funds(0)
    assert scores[p3.id]["breakdown"]["funds_bonus"] == 0
