from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import (
    COMPUTE_UPGRADE_COSTS,
    COMPUTE_NET_WORTH_REQ,
    MODEL_NET_WORTH_REQ,
    WORLD_MAP,
    NET_WORTH_COSTS,
    RECRUIT_COSTS,
    PRESENCE_COSTS,
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
# 1. CORE UTILITIES & HELPERS
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


def apply_card_effect(db: Session, player_id: int, card_id: int):
    """
    Identifies the card's effect slug and executes the corresponding logic.
    """
    # Local import to break circular dependency
    from backend.card_effects import CARD_EFFECT_REGISTRY

    card = db.get(Component, card_id)
    if not card:
        return {"error": "Card not found."}

    effect_slug = card.card_details.effect_slug

    if effect_slug in CARD_EFFECT_REGISTRY:
        return CARD_EFFECT_REGISTRY[effect_slug](db, player_id, card_id)

    return {"error": f"No logic implemented for effect: {effect_slug}"}


def calculate_nw_vp(rank: int, player_count: int) -> int:
    """Helper to determine Net Worth VP Bonus based on player count."""
    if player_count == 2:
        return 1 if rank == 1 else 0

    if player_count == 3:
        if rank == 1:
            return 2
        if rank == 2:
            return 1
        return 0

    if player_count >= 4:
        if rank == 1:
            return 2
        if rank in [2, 3]:
            return 1
        return 0

    return 0


def calculate_game_leaderboard(db: Session, game_id: int):
    """
    Calculates total VP for all players in a game, including
    competitive ranking bonuses (Personal Funds).
    """
    players = db.query(Player).filter(Player.game_id == game_id).all()
    player_count = len(players)

    # 1. Rank players by Personal Funds for the cash bonus
    # Sort descending: highest funds first
    sorted_by_funds = sorted(players, key=lambda p: p.personal_funds, reverse=True)

    fund_bonuses = {}
    if player_count == 2:
        fund_bonuses[sorted_by_funds[0].id] = 3
    elif player_count == 3:
        fund_bonuses[sorted_by_funds[0].id] = 3
        fund_bonuses[sorted_by_funds[1].id] = 1
    elif player_count >= 4:
        fund_bonuses[sorted_by_funds[0].id] = 3
        fund_bonuses[sorted_by_funds[1].id] = 2
        fund_bonuses[sorted_by_funds[2].id] = 1

    leaderboard = []
    for player in players:
        # Base VP from race bonuses (Millionaire/Billionaire first-to-finish)
        total_vp = player.vp
        # 1. 1VP for each 5 Power
        total_vp += player.power // 5
        # 2. 1VP for each Model Version
        total_vp += player.model_version
        # 3. 1VP per Region with Presence
        total_vp += player.presence_count
        # 4. Personal Funds Ranking Bonus
        total_vp += fund_bonuses.get(player.id, 0)

        leaderboard.append(
            {
                "player_id": player.id,
                "user_name": player.user_name,
                "total_vp": total_vp,
                "breakdown": {
                    "race_bonuses": player.vp,
                    "power_vp": player.power // 5,
                    "model_vp": player.model_version,
                    "presence_vp": player.presence_count,
                    "funds_bonus": fund_bonuses.get(player.id, 0),
                },
            }
        )

    # Sort leaderboard by total VP for display
    return sorted(leaderboard, key=lambda x: x["total_vp"], reverse=True)


# ==========================================
# 2. QUARTERLY STRATEGY ACTIONS
# ==========================================


def get_projected_player_state(db: Session, player_id: int, up_to_worker_number: int):
    """
    Simulates the state of the player after executing all workers < up_to_worker_number.
    Returns a dict-like object (or just a dict) with the projected stats.
    """
    player = db.get(Player, player_id)
    
    # Base state
    state = {
        "compute_level": player.compute_level,
        "model_version": player.model_version,
        "net_worth_level": player.net_worth_level,
        "corporate_funds": player.corporate_funds,
        "reputation": player.reputation,
        "total_workers": player.total_workers,
        "presence_count": player.presence_count,
        "income": player.income, # Simplified, income updates are complex but usually stable within turn except for upgrades
    }
    
    # Fetch active modifiers for more accurate simulation? 
    # For now, let's assume basic modifiers are static or we re-fetch them.
    # Actually, modifiers depend on Tiles, which shouldn't change mid-turn usually (unless we steal).
    mods = get_player_modifiers(db, player_id)

    # Fetch all placements for this player
    placements = (
        db.query(WorkerPlacement)
        .filter(
            WorkerPlacement.player_id == player_id,
            WorkerPlacement.worker_number < up_to_worker_number
        )
        .order_by(WorkerPlacement.worker_number.asc())
        .all()
    )

    for p in placements:
        # Simulate effects of p.action_type
        if p.action_type == "raise_funds":
            # Simulation matches execute_raise_funds_sequence:
            # 1. Existing Corporate Funds move to Personal (siphoned)
            # 2. Corporate Funds reset to 0
            # 3. New Income is added (capped)
            
            # Note: We don't strictly *need* to track personal_funds for validation 
            # (validation only checks limits/availability), but let's be accurate.
            # state["personal_funds"] += state["corporate_funds"] 
            
            # Siphon
            state["corporate_funds"] = 0
            
            # Determine Gain
            # If multiple workers were placed individually, they might count as separate chunks.
            # However, in this loop we process them linearly 1 by 1.
            # Single worker cap is 8.
            gain = min(state["income"], 8)
            
            if mods["worker_income_efficiency"]:
                gain = min(state["income"], 39)
            
            state["corporate_funds"] += gain

        elif p.action_type == "buy_chips":
            next_lvl = state["compute_level"] + 1
            if next_lvl <= 7:
                cost = COMPUTE_UPGRADE_COSTS.get(next_lvl, 0)
                final_cost = max(0, cost + mods["compute_cost_offset"])
                if state["corporate_funds"] >= final_cost:
                    state["corporate_funds"] -= final_cost
                    state["compute_level"] = next_lvl

        elif p.action_type == "marketing":
            bonus = MARKETING_BONUSES.get(state["net_worth_level"])
            if bonus:
                state["reputation"] = min(10, state["reputation"] + bonus["reputation"])
                # Power update ignored for validation purposes usually

        elif p.action_type == "increase_net_worth":
            next_nw = state["net_worth_level"] + 1
            if next_nw <= 2:
                costs = NET_WORTH_COSTS.get(next_nw)
                if state["corporate_funds"] >= costs["money"] and (state["reputation"] - costs["reputation"]) >= -3:
                    state["corporate_funds"] -= costs["money"]
                    state["reputation"] -= costs["reputation"]
                    state["net_worth_level"] = next_nw

        elif p.action_type == "recruit":
            next_num = state["total_workers"] + 1
            if next_num <= 8:
                tier = RECRUIT_COSTS.get(next_num)
                # Ensure we have funds
                if state["corporate_funds"] >= tier["money"] and state["net_worth_level"] >= tier["min_nw"]:
                    state["corporate_funds"] -= tier["money"]
                    state["total_workers"] = next_num

        elif p.action_type == "scale_presence":
            # Presence count starts at 1 usually (Capital).
            # If 1 presence, next is 2. Cost index 0.
            # State needs presence_count.
            # Wait, `get_projected_player_state` init didn't include `presence_count`. 
            # I must fix that too.
            current_presence = state.get("presence_count", 1) # Default to 1 if missing in my init logic (I need to add it)
            cost_idx = current_presence - 1
            if cost_idx < len(PRESENCE_COSTS):
                cost = PRESENCE_COSTS[cost_idx]
                if state["corporate_funds"] >= cost:
                    state["corporate_funds"] -= cost
                    state["presence_count"] = current_presence + 1

        elif p.action_type == "train_model":
            # Track worker accumulation for model training
            if "train_workers_accumulated" not in state:
                state["train_workers_accumulated"] = 0
            
            state["train_workers_accumulated"] += 1
            
            # Check if an upgrade is triggered
            next_version = state["model_version"] + 1
            if next_version <= 7:
                base_req = MODEL_WORKER_COSTS.get(next_version, 1)
                req = max(1, base_req + mods["model_worker_cost_offset"])
                
                if state["train_workers_accumulated"] >= req:
                    state["model_version"] = next_version
                    state["train_workers_accumulated"] = 0

    return state


def validate_buy_chips(db: Session, player_id: int, projected_state: dict):
    """Checks requirements for Buy Chips using projected state."""
    next_level = projected_state["compute_level"] + 1
    mods = get_player_modifiers(db, player_id)

    if next_level > 7:
        return {"error": "Maximum compute level already reached."}

    base_cost = COMPUTE_UPGRADE_COSTS.get(next_level)
    final_cost = max(0, base_cost + mods["compute_cost_offset"])

    if projected_state["corporate_funds"] < final_cost:
        return {"error": f"Insufficient funds. Need ${final_cost}."}

    required_nw = COMPUTE_NET_WORTH_REQ.get(next_level, 0)
    if projected_state["net_worth_level"] < required_nw:
        # User requested specific checking. If we have funds but low NW:
        return {"error": "Net Worth too low."}

    return None


def validate_recruit(db: Session, player_id: int, projected_state: dict):
    """Checks requirements for Recruit using projected state."""
    next_num = projected_state["total_workers"] + 1
    if next_num > 8:
        return {"error": "Max workers reached."}

    tier = RECRUIT_COSTS[next_num]
    if (
        projected_state["corporate_funds"] < tier["money"]
        or projected_state["net_worth_level"] < tier["min_nw"]
    ):
        return {"error": "Requirements not met for recruitment."}
    return None


def validate_train_model(db: Session, player_id: int, projected_state: dict):
    """Checks requirements using projected state."""
    next_version = projected_state["model_version"] + 1
    if next_version > 7:
        return {"error": "Maximum Model Version reached."}

    if projected_state["compute_level"] < next_version:
        return {"error": f"Insufficient Compute Level. Need {next_version}."}

    if projected_state["net_worth_level"] < MODEL_NET_WORTH_REQ.get(next_version, 0):
        return {"error": "Net Worth too low for this Model Version."}
    return None


def validate_increase_net_worth(db: Session, player_id: int, projected_state: dict):
    """Checks requirements using projected state."""
    next_nw = projected_state["net_worth_level"] + 1

    if next_nw > 2:
        return {"error": "Already a Billionaire."}

    costs = NET_WORTH_COSTS[next_nw]
    if projected_state["corporate_funds"] < costs["money"]:
        return {"error": f"Insufficient funds. Need ${costs['money']}."}
    if (projected_state["reputation"] - costs["reputation"]) < -3:
        return {"error": "Reputation too low."}
    return None


def validate_scale_presence(db: Session, player_id: int, projected_state: dict):
    """Checks requirements for Scale Presence using projected state."""
    current_presence = projected_state.get("presence_count", 1)
    
    # Check max presence? Map has 10 regions. Assuming max 10.
    if current_presence >= 10:
        return {"error": "Maximum presence reached."}
    
    # Cost Index: Presence 1 -> Next is 2. cost_idx = 2-2 = 0.
    # Logic in frontend was: val-2. 
    # Current presence 1. Next is 2. Cost is PRESENCE_COSTS[0].
    # So index = current_presence - 1?
    # Wait, PRESENCE_COSTS = [1, 3, 4...] (Cost for 2nd, 3rd...)
    # If I have 1 presence, next is 2nd. Index 0. 
    # So index = count - 1.
    cost_idx = current_presence - 1
    if cost_idx >= len(PRESENCE_COSTS):
         # Fallback max cost?
         cost = PRESENCE_COSTS[-1]
    else:
        cost = PRESENCE_COSTS[cost_idx]

    if projected_state["corporate_funds"] < cost:
        return {"error": f"Insufficient funds. Need ${cost}."}

    return None


def execute_buy_chips(db: Session, player_id: int):
    """Resolves the Buy Chips action."""
    # Note: Validation is done at placement time now, but we double-check or trust the state?
    # For execution, we just execute on current state.
    # The original function called validate_buy_chips.
    # We should keep it safe. But validate_buy_chips now requires projected_state.
    # In execution context, current state IS the projected state (roughly).
    
    player = db.get(Player, player_id)
    mods = get_player_modifiers(db, player_id)
    
    # We can reconstruct the "current validation" by passing current state as projected
    current_state = {
        "compute_level": player.compute_level,
        "corporate_funds": player.corporate_funds,
        "net_worth_level": player.net_worth_level
    }
    error = validate_buy_chips(db, player_id, current_state)
    if error:
        return error

    next_level = player.compute_level + 1
    base_cost = COMPUTE_UPGRADE_COSTS.get(next_level)
    final_cost = max(0, base_cost + mods["compute_cost_offset"])

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

    # Determine Cost and Deduct Funds
    # Current count BEFORE adding this one
    current_count = player.presence_count
    cost_idx = current_count - 1
    if cost_idx < 0: cost_idx = 0 # Should happen only if count 0?
    if cost_idx >= len(PRESENCE_COSTS):
        cost = PRESENCE_COSTS[-1]
    else:
        cost = PRESENCE_COSTS[cost_idx]

    if player.corporate_funds < cost:
        return {"error": f"Insufficient funds. Need ${cost}."}

    player.corporate_funds -= cost

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
    player = db.get(Player, player_id)
    game = db.get(Game, player.game_id)
    next_nw = player.net_worth_level + 1

    if next_nw > 2:
        return {"error": "Already a Billionaire."}

    costs = NET_WORTH_COSTS[next_nw]
    if player.corporate_funds < costs["money"]:
        return {"error": f"Insufficient funds. Need ${costs['money']}."}
    if (player.reputation - costs["reputation"]) < -3:
        return {"error": "Reputation too low."}

    # 1. Deduct costs and upgrade
    player.corporate_funds -= costs["money"]
    player.reputation -= costs["reputation"]
    player.net_worth_level = next_nw

    # 2. Handle VP Bonuses
    player_count = db.query(Player).filter(Player.game_id == game.id).count()
    vp_reward = 0

    if next_nw == 1:  # Becoming Millionaire
        game.millionaire_count += 1
        rank = game.millionaire_count
        vp_reward = calculate_nw_vp(rank, player_count)

    elif next_nw == 2:  # Becoming Billionaire
        game.billionaire_count += 1
        rank = game.billionaire_count
        vp_reward = calculate_nw_vp(rank, player_count)

    player.vp += vp_reward

    # 3. State cleanup
    update_player_income(db, player)
    check_reputation_tiles(db, player_id)
    db.commit()

    return {
        "action": "net_worth_increased",
        "new_level": player.net_worth_level,
        "vp_gained": vp_reward,
        "total_vp": player.vp,
    }


def execute_recruit_worker(db: Session, player_id: int, target_action: str):
    """Resolves the Recruit action and immediately places the new worker."""
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
    
    # Immediately place the new worker on the board in the chosen slot
    db.add(
        WorkerPlacement(
            game_id=player.game_id,
            player_id=player_id,
            worker_number=next_num,
            action_type=target_action,
        )
    )
    db.commit()
    return {
        "action": "worker_recruited", 
        "new_total": player.total_workers,
        "placed_at": target_action
    }


def execute_raise_funds_sequence(db: Session, player_id: int, chunks: list[int]):
    """Resolves Raise Funds with Automated Finance modifiers."""
    player = db.get(Player, player_id)
    mods = get_player_modifiers(db, player_id)
    summary = []

    # Siphon once at the start of the execution sequence
    total_siphoned = player.corporate_funds
    player.personal_funds += total_siphoned
    player.corporate_funds = 0
    
    total_drawn = 0
    for worker_count in chunks:
        if worker_count < 1:
            continue
            
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
        total_drawn += drawn
        summary.append({"workers": worker_count, "drawn": drawn})

    player.corporate_funds = total_drawn
    db.commit()
    return {"action": "raise_funds_resolved", "total_siphoned": total_siphoned, "total_drawn": total_drawn, "sequence": summary}


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


def validate_placement_count(db: Session, player_id: int, action_type: str, worker_number: int):
    """Checks if placing another worker on this action exceeds allowed limits."""
    # Count existing workers on this action, EXCLUDING the current worker if already there
    existing_count = (
        db.query(WorkerPlacement)
        .filter(
            WorkerPlacement.player_id == player_id,
            WorkerPlacement.action_type == action_type,
            WorkerPlacement.worker_number != worker_number,
        )
        .count()
    )
    current_total = existing_count + 1

    # 1. Single-Worker Actions (Redundant/Invalid with >1)
    # USER UPDATE: these are NOT restricted. Players can buy multiple chips/recruit multiple workers if they can afford it.
    pass

    # 2. Train Model (Relaxed to allow multiple upgrades)
    if action_type == "train_model":
        # We allow placing as many workers as the player has compute/eligibility for.
        # This is finalized in validate_action_requirements which uses projection.
        pass

    # 3. Raise Funds (Soft Cap at 3 for max efficiency, 4+ is wasted)
    if action_type == "raise_funds":
        if current_total > 3:
            return {"error": "Max efficiency reached with 3 workers. Additional workers provide no benefit."}

    return None

def validate_action_requirements(db: Session, player_id: int, action_type: str, worker_number: int):
    """Checks if the player meets the requirements for a proposed action, accounting for previous workers."""
    
    # Calculate projected state
    projected_state = get_projected_player_state(db, player_id, worker_number)

    if action_type == "buy_chips":
        return validate_buy_chips(db, player_id, projected_state)
    elif action_type == "recruit":
        return validate_recruit(db, player_id, projected_state)
    elif action_type == "train_model":
        return validate_train_model(db, player_id, projected_state)
    elif action_type == "increase_net_worth":
        return validate_increase_net_worth(db, player_id, projected_state)
    elif action_type == "scale_presence":
        return validate_scale_presence(db, player_id, projected_state)
    
    return None


def place_worker(db: Session, player_id: int, worker_number: int, action_type: str):
    """
    Validates and places (or updates) a worker on a specific action slot.
    """
    player = db.get(Player, player_id)

    # 1. Calculate projected state to handle "future" workers from recruitment
    projected_state = get_projected_player_state(db, player_id, worker_number)

    # 2. Validation: Does player own this worker (or will they?)
    if worker_number > projected_state["total_workers"]:
        return {"error": f"Player only has {player.total_workers} workers (projected: {projected_state['total_workers']})."}

    # 3. Validation: Placement Limits (Count check)
    count_error = validate_placement_count(db, player_id, action_type, worker_number)
    if count_error:
        return count_error

    # 3. Validation: Does player meet the requirements for the action?
    req_error = validate_action_requirements(db, player_id, action_type, worker_number)
    if req_error:
        return req_error

    # 4. Upsert: Update if exists, otherwise create
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
    leaderboard = calculate_game_leaderboard(db, game_id)
    db.commit()
    return {
        "action": "round_resolved",
        "new_p1_index": game.p1_token_index,
        "leaderboard": leaderboard,
    }
def undo_last_placement(db: Session, player_id: int):
    """Removes the highest numbered worker placement for the given player."""
    last_placement = (
        db.query(WorkerPlacement)
        .filter_by(player_id=player_id)
        .order_by(WorkerPlacement.worker_number.desc())
        .first()
    )
    if not last_placement:
        return {"error": "No workers placed to undo."}

    worker_num = last_placement.worker_number
    action = last_placement.action_type
    db.delete(last_placement)
    db.commit()
    return {
        "action": "worker_removed",
        "worker_number": worker_num,
        "from_action": action,
    }
