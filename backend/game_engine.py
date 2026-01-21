from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import (
    COMPUTE_UPGRADE_COSTS,
    COMPUTE_NET_WORTH_REQ,
    MODEL_NET_WORTH_REQ,
    WORLD_MAP,
    NET_WORTH_COSTS,
    RECRUIT_COSTS,
    MODEL_WORKER_COSTS,
    MARKETING_BONUSES,
)
from backend.models import (
    Component,
    Player,
    WorkerPlacement,
    Game,
    Presence,
    RegionState,
    ReputationTile,
)
from backend.seed import ZoneType

# ==========================================
# 1. CORE UTILITIES & STATE HELPERS
# ==========================================


def get_player_modifiers(db: Session, player_id: int):
    """
    Returns a dictionary of active buffs and penalties for the player.
    """
    mods = {
        "model_worker_cost_offset": 0,
        "compute_cost_offset": 0,
        "hand_limit": 5,
        "income_offset": 0,
        "draw_bonus": 0,
        "worker_income_efficiency": False,
        "free_card_play": False,
        "priority_p1": False,
    }

    tiles = db.query(ReputationTile).filter_by(owner_id=player_id).all()

    for tile in tiles:
        code = tile.effect_code
        if code == "model_cost_plus_1":
            mods["model_worker_cost_offset"] += 1
        elif code == "model_worker_minus_1":
            mods["model_worker_cost_offset"] -= 1
        elif code == "compute_cost_plus_3":
            mods["compute_cost_offset"] += 3
        elif code == "compute_minus_1":
            mods["compute_cost_offset"] -= 1
        elif code == "compute_minus_2":
            mods["compute_cost_offset"] -= 2
        elif code == "hand_limit_3":
            mods["hand_limit"] = min(mods["hand_limit"], 3)
        elif code == "hand_limit_6":
            mods["hand_limit"] = 6
        elif code == "income_plus_1":
            mods["income_offset"] += 1
        elif code == "income_plus_2":
            mods["income_offset"] += 2
        elif code == "one_worker_income":
            mods["worker_income_efficiency"] = True
        elif code == "draw_extra_card":
            mods["draw_bonus"] += 1
        elif code == "perma_p1":
            mods["priority_p1"] = True

    return mods


def update_player_income(db: Session, player: Player):
    """Calculates and updates player income based on stats and tiles."""
    mods = get_player_modifiers(db, player.id)
    multiplier = player.net_worth_level
    base_income = player.power + (player.subsidy_tokens * multiplier)

    player.income = min(39, base_income + mods["income_offset"])


def check_reputation_tiles(db: Session, player_id: int):
    """Handles stealing logic and eligibility for Reputation Tiles."""
    player = db.get(Player, player_id)
    game_id = player.game_id

    # Level 0 Check (Penalty)
    current_penalty = (
        db.query(ReputationTile).filter_by(owner_id=player.id, level=0).first()
    )
    if player.reputation == -3 and not current_penalty:
        available = (
            db.query(ReputationTile)
            .filter_by(game_id=game_id, level=0, owner_id=None)
            .first()
        )
        if available:
            available.owner_id = player.id
    elif player.reputation > -3 and current_penalty:
        current_penalty.owner_id = None

    # Levels 1-3 Stealing/Eligibility
    for level in [1, 2, 3]:
        if level == 2 and player.net_worth_level < 1:
            continue
        if level == 3 and player.net_worth_level < 2:
            continue

        min_rep = {1: 1, 2: 6, 3: 10}[level]
        if player.reputation < min_rep:
            continue

        tiles = db.query(ReputationTile).filter_by(game_id=game_id, level=level).all()
        for tile in tiles:
            if tile.owner_id is None:
                tile.owner_id = player.id
                break
            owner = db.get(Player, tile.owner_id)
            if player.reputation > owner.reputation:
                tile.owner_id = player.id
                break
    db.commit()


# ==========================================
# 2. QUARTERLY STRATEGY ACTIONS
# ==========================================


def execute_buy_chips(db: Session, player_id: int):
    """Resolves the Buy Chips action."""
    player = db.get(Player, player_id)
    next_level = player.compute_level + 1
    mods = get_player_modifiers(db, player_id)

    if next_level > 7:
        return {"error": "Maximum compute level already reached."}

    base_cost = COMPUTE_UPGRADE_COSTS.get(next_level)
    final_cost = max(0, base_cost + mods["compute_cost_offset"])

    if player.corporate_funds < final_cost:
        return {"error": f"Insufficient funds. Need ${final_cost}."}

    required_nw = COMPUTE_NET_WORTH_REQ.get(next_level, 0)
    if player.net_worth_level < required_nw:
        return {"error": "Net Worth too low."}

    player.corporate_funds -= final_cost
    player.compute_level = next_level
    db.commit()
    return {"action": "compute_upgraded", "new_level": player.compute_level}


def execute_train_model(db: Session, player_id: int, worker_count: int = 1):
    """Resolves the Train Model action with tile modifiers."""
    player = db.get(Player, player_id)
    mods = get_player_modifiers(db, player_id)

    next_version = player.model_version + 1
    if next_version > 7:
        return {"error": "Maximum Model Version reached."}

    base_req = MODEL_WORKER_COSTS.get(next_version, 1)
    final_worker_req = max(1, base_req + mods["model_worker_cost_offset"])

    if worker_count < final_worker_req:
        return {
            "error": f"Insufficient Tech Workers. Need {final_worker_req} for this upgrade."
        }

    if player.compute_level < next_version:
        return {"error": f"Insufficient Compute Level. Need {next_version}."}

    if player.net_worth_level < MODEL_NET_WORTH_REQ.get(next_version, 0):
        return {"error": "Net Worth too low for this Model Version."}

    player.model_version = next_version
    player.reputation = min(10, player.reputation + 1)
    player.power = min(40, player.power + (player.presence_count // 2))

    update_player_income(db, player)
    check_reputation_tiles(db, player_id)
    db.commit()
    return {
        "action": "model_trained",
        "new_version": player.model_version,
        "new_power": player.power,
        "new_income": player.income,
    }


def execute_marketing(db: Session, player_id: int):
    """Resolves the Marketing action."""
    player = db.get(Player, player_id)
    bonus = MARKETING_BONUSES.get(player.net_worth_level)

    player.reputation = min(10, player.reputation + bonus["reputation"])
    player.power = min(40, player.power + bonus["power"])

    update_player_income(db, player)
    check_reputation_tiles(db, player_id)
    db.commit()
    return {"action": "marketing_resolved", "new_reputation": player.reputation}


def execute_scale_presence(db: Session, player_id: int, target_region: int):
    """Resolves the Scale Presence action."""
    player = db.get(Player, player_id)
    existing = (
        db.query(Presence)
        .filter_by(player_id=player_id, region_id=target_region)
        .first()
    )
    if existing:
        return {"error": "Already present in this region."}

    current_region_ids = [
        p.region_id for p in db.query(Presence).filter_by(player_id=player_id).all()
    ]
    if not any(target_region in WORLD_MAP.get(r_id, []) for r_id in current_region_ids):
        return {"error": "Region not adjacent."}

    db.add(Presence(player_id=player_id, region_id=target_region))
    player.presence_count += 1

    region_state = (
        db.query(RegionState)
        .filter_by(game_id=player.game_id, region_id=target_region)
        .first()
    )
    if region_state and region_state.subsidy_tokens_remaining > 0:
        region_state.subsidy_tokens_remaining -= 1
        player.subsidy_tokens += 1
        update_player_income(db, player)

    db.commit()
    return {"action": "presence_scaled", "new_region": target_region}


def execute_increase_net_worth(db: Session, player_id: int):
    """Resolves the Increase Net Worth action."""
    player = db.get(Player, player_id)
    next_nw = player.net_worth_level + 1

    if next_nw > 2:
        return {"error": "Already a Billionaire."}
    costs = NET_WORTH_COSTS[next_nw]

    if player.corporate_funds < costs["money"]:
        return {"error": f"Insufficient funds. Need ${costs['money']}."}
    if (player.reputation - costs["reputation"]) < -3:
        return {"error": "Reputation too low."}

    player.corporate_funds -= costs["money"]
    player.reputation -= costs["reputation"]
    player.net_worth_level = next_nw

    update_player_income(db, player)
    check_reputation_tiles(db, player_id)
    db.commit()
    return {"action": "net_worth_increased", "new_level": player.net_worth_level}


def execute_recruit_worker(db: Session, player_id: int, target_action: str):
    """Resolves the Recruit action."""
    player = db.get(Player, player_id)
    next_num = player.total_workers + 1
    if next_num > 8:
        return {"error": "Max workers reached."}

    tier = RECRUIT_COSTS[next_num]
    if (
        player.corporate_funds < tier["money"]
        or player.net_worth_level < tier["min_nw"]
    ):
        return {"error": "Requirements not met for recruitment."}

    player.corporate_funds -= tier["money"]
    player.total_workers = next_num
    db.add(
        WorkerPlacement(
            game_id=player.game_id,
            player_id=player_id,
            worker_number=next_num,
            action_type=target_action,
        )
    )
    db.commit()
    return {"action": "worker_recruited", "new_total": player.total_workers}


def execute_raise_funds_sequence(db: Session, player_id: int, chunks: list[int]):
    """Resolves Raise Funds with Automated Finance modifiers."""
    player = db.get(Player, player_id)
    mods = get_player_modifiers(db, player_id)
    summary = []

    for worker_count in chunks:
        if worker_count < 1:
            continue
        siphoned = player.corporate_funds
        player.personal_funds += siphoned
        player.corporate_funds = 0

        if mods["worker_income_efficiency"]:
            cap = 39
        else:
            if worker_count == 1:
                cap = 8
            elif worker_count == 2:
                cap = 19
            else:
                cap = 39

        drawn = min(player.income, cap)
        player.corporate_funds = drawn
        summary.append({"workers": worker_count, "siphoned": siphoned, "drawn": drawn})

    db.commit()
    return {"action": "raise_funds_resolved", "sequence": summary}


# ==========================================
# 3. CARD & COMPONENT LOGIC
# ==========================================


def draw_card(db: Session, player_id: int, deck_type: ZoneType):
    """Low-level draw logic."""
    player = db.get(Player, player_id)
    card = (
        db.query(Component)
        .filter(Component.zone == deck_type.value, Component.game_id == player.game_id)
        .first()
    )
    if not card:
        return {"error": f"No cards left in {deck_type.value}"}

    card.zone = f"hand_p{player_id}"
    card.owner_id = player_id
    card.is_face_up = False
    return {"action": "card_drawn", "new_zone": card.zone, "component_id": card.id}


def execute_round_start_draw(db: Session, player_id: int, bonus_deck: ZoneType = None):
    """Batch draw at round start with choice-based bonus."""
    mods = get_player_modifiers(db, player_id)
    results = [
        draw_card(db, player_id, d)
        for d in [
            ZoneType.RESEARCH_DECK,
            ZoneType.INFLUENCE_DECK,
            ZoneType.SABOTAGE_DECK,
        ]
    ]

    if mods["draw_bonus"] > 0:
        if not bonus_deck:
            return {"error": "Bonus draw choice required."}
        results.append(draw_card(db, player_id, bonus_deck))

    db.commit()
    hand_count = (
        db.query(Component)
        .filter(Component.owner_id == player_id, Component.zone == f"hand_p{player_id}")
        .count()
    )

    if hand_count > mods["hand_limit"]:
        return {
            "status": "must_discard",
            "count": hand_count - mods["hand_limit"],
            "results": results,
        }
    return {"status": "success", "results": results}


def discard_card(db: Session, player_id: int, card_id: int):
    """Discards a card to its sub-type pile."""
    card = db.get(Component, card_id)
    if not card or card.owner_id != player_id:
        return {"error": "Invalid card."}
    card.zone = f"{card.sub_type}_discard"
    card.owner_id = None
    db.commit()
    return {"action": "card_discarded", "card_id": card_id}


def move_piece(db: Session, component_id: int, new_x: float, new_y: float):
    """Updates physical board coordinates."""
    piece = db.query(Component).get(component_id)
    if piece:
        piece.pos_x, piece.pos_y = new_x, new_y
        piece.z_index += 1
        db.commit()
        return {"success": True}
    return {"error": "Piece not found"}


def play_card(db: Session, player_id: int, card_id: int, target_slot: int = None):
    """Moves a card to active slot or discard."""
    card = db.get(Component, card_id)
    if not card or card.owner_id != player_id:
        return {"error": "Not owner."}

    if card.card_details.is_effect:
        if not target_slot or not (1 <= target_slot <= 3):
            return {"error": "Invalid slot."}
        target_zone = f"active_effect_card_slot_{target_slot}_p{player_id}"
        existing = (
            db.query(Component)
            .filter_by(zone=target_zone, game_id=card.game_id)
            .first()
        )
        if existing:
            existing.zone, existing.owner_id = f"{existing.sub_type}_discard", None
        card.zone = target_zone
    else:
        card.zone, card.owner_id = f"{card.sub_type}_discard", None

    db.commit()
    return {"action": "card_played", "new_zone": card.zone}


# ==========================================
# 4. ROUND RESOLUTION & DISPATCH
# ==========================================


def get_sorted_players(
    db: Session, players: list[Player], p1_token_index: int
) -> list[Player]:
    """Sorts players clockwise, prioritizing Board Chairman tile."""
    priority_p = next(
        (p for p in players if get_player_modifiers(db, p.id)["priority_p1"]), None
    )
    effective_start = priority_p.player_order if priority_p else p1_token_index
    players_by_order = sorted(players, key=lambda x: x.player_order)
    return [
        players_by_order[(effective_start + i) % len(players)]
        for i in range(len(players))
    ]


def place_worker(db: Session, player_id: int, worker_number: int, action_type: str):
    """
    Validates and places (or updates) a worker on a specific action slot.
    """
    player = db.get(Player, player_id)

    # 1. Validation: Does player own this worker?
    if worker_number > player.total_workers:
        return {"error": f"Player only has {player.total_workers} workers."}

    # 2. Upsert: Update if exists, otherwise create
    placement = (
        db.query(WorkerPlacement)
        .filter(
            WorkerPlacement.player_id == player_id,
            WorkerPlacement.worker_number == worker_number,
            WorkerPlacement.game_id == player.game_id,
        )
        .first()
    )

    if placement:
        placement.action_type = action_type
    else:
        placement = WorkerPlacement(
            game_id=player.game_id,
            player_id=player_id,
            worker_number=worker_number,
            action_type=action_type,
        )
        db.add(placement)

    db.commit()
    return {
        "action": "worker_placed",
        "worker_number": worker_number,
        "slot": action_type,
    }


def execute_action(
    db: Session, player_id: int, action_type: str, worker_count: int = 1
):
    """Routes strategy slot actions to handlers."""
    if action_type == "raise_funds":
        return execute_raise_funds_sequence(db, player_id, [worker_count])
    if action_type == "train_model":
        return execute_train_model(db, player_id, worker_count)
    if action_type == "buy_chips":
        return execute_buy_chips(db, player_id)
    if action_type == "marketing":
        return execute_marketing(db, player_id)
    if action_type == "recruit":
        return execute_recruit_worker(db, player_id, "marketing")
    if action_type == "increase_net_worth":
        return execute_increase_net_worth(db, player_id)
    if action_type == "scale_presence":
        return execute_scale_presence(db, player_id, 1)  # Placeholder region
    return {"error": "Action unrecognized"}


def resolve_entire_round(db: Session, game_id: int):
    """Processes all quarterly strategies numerically."""
    game = db.get(Game, game_id)
    players = db.query(Player).filter_by(game_id=game_id).all()
    for player in get_sorted_players(db, players, game.p1_token_index):
        resolved = set()
        while True:
            p = (
                db.query(WorkerPlacement)
                .filter(
                    WorkerPlacement.player_id == player.id,
                    WorkerPlacement.worker_number.notin_(resolved),
                )
                .order_by(WorkerPlacement.worker_number.asc())
                .first()
            )
            if not p:
                break

            group = (
                db.query(WorkerPlacement)
                .filter_by(player_id=player.id, worker_number=p.worker_number)
                .all()
            )
            execute_action(db, player.id, p.action_type, len(group))
            for w in group:
                resolved.add(w.worker_number)

    game.p1_token_index = (game.p1_token_index + 1) % len(players)
    db.query(WorkerPlacement).filter_by(game_id=game_id).delete()
    db.commit()
    return {"action": "round_resolved", "new_p1_index": game.p1_token_index}
