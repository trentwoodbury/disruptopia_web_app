from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import COMPUTE_UPGRADE_COSTS, COMPUTE_NET_WORTH_REQ, MODEL_NET_WORTH_REQ, WORLD_MAP, \
    NET_WORTH_COSTS, RECRUIT_COSTS, MODEL_WORKER_COSTS, MARKETING_BONUSES
from backend.models import Component, Player, CardDetails, WorkerPlacement, Game, Presence, RegionState
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


def buy_chips(db: Session, player_id: int):
    player = db.get(Player, player_id)
    next_level = player.compute_level + 1

    # 1. Check if already at max level
    if next_level > 7:
        return {"error": "Maximum compute level already reached."}

    # 2. Check Corporate Funds
    cost = COMPUTE_UPGRADE_COSTS.get(next_level)
    if player.corporate_funds < cost:
        return {"error": f"Insufficient funds. Need ${cost}, have ${player.corporate_funds}."}

    # 3. Check Net Worth Gate
    required_nw = COMPUTE_NET_WORTH_REQ.get(next_level, 0) # Default to Startup (0)
    if player.net_worth_level < required_nw:
        nw_name = "Millionaire" if required_nw == 1 else "Billionaire"
        return {"error": f"Net Worth too low. Upgrade to {nw_name} first."}

    # 4. Execute Upgrade
    player.corporate_funds -= cost
    player.compute_level = next_level
    db.commit()

    return {
        "action": "compute_upgraded",
        "new_level": player.compute_level,
        "remaining_funds": player.corporate_funds
    }


def train_model(db: Session, player_id: int, worker_count: int = 1):
    player = db.get(Player, player_id)

    # 1. INITIAL GATE CHECKS (Preserves your error-dependent tests)
    next_version = player.model_version + 1
    if next_version > 7:
        return {"error": "Maximum Model Version reached."}

    if player.compute_level < next_version:
        return {"error": f"Insufficient Compute Level. Need {next_version}."}

    required_nw = MODEL_NET_WORTH_REQ.get(next_version, 0)
    if player.net_worth_level < required_nw:
        return {"error": "Net Worth too low for this Model Version."}

    # 2. ACCUMULATE PROGRESS
    player.model_version = next_version
    player.reputation = min(10, player.reputation + 1)
    power_upgrade = player.presence_count // 2
    player.power = min(40, player.power + power_upgrade)
    update_player_income(player)

    db.commit()

    # Return structure satisfies both the logic tests and the scenario tests
    return {
        "action": "model_trained",
        "new_version": player.model_version,
        "new_power": player.power,
        "new_income": player.income
    }


def scale_presence(db: Session, player_id: int, target_region: int):
    player = db.get(Player, player_id)

    # 1. Check if already present
    existing = db.query(Presence).filter_by(player_id=player_id, region_id=target_region).first()
    if existing:
        return {"error": "Player already has presence in this region."}

    # 2. Check Adjacency
    # Get all regions where the player currently has presence
    current_presences = db.query(Presence).filter_by(player_id=player_id).all()
    current_region_ids = [p.region_id for p in current_presences]

    is_adjacent = False
    for r_id in current_region_ids:
        if target_region in WORLD_MAP.get(r_id, []):
            is_adjacent = True
            break

    if not is_adjacent:
        return {"error": f"Region {target_region} is not adjacent to your current presence."}

    # 3. Execute Movement
    new_presence = Presence(player_id=player_id, region_id=target_region)
    db.add(new_presence)
    player.presence_count += 1

    # 4. Claim Subsidy Token if available
    region_state = db.query(RegionState).filter_by(
        game_id=player.game_id,
        region_id=target_region
    ).first()

    claimed = False
    if region_state and region_state.subsidy_tokens_remaining > 0:
        region_state.subsidy_tokens_remaining -= 1
        player.subsidy_tokens += 1
        claimed = True
        # Update income because subsidy count changed
        update_player_income(player)

    db.commit()
    return {
        "action": "presence_scaled",
        "new_region": target_region,
        "subsidy_claimed": claimed,
        "new_total_subsidies": player.subsidy_tokens,
        "new_income": player.income
    }


def increase_net_worth(db: Session, player_id: int):
    player = db.get(Player, player_id)
    next_nw = player.net_worth_level + 1

    if next_nw > 2:
        return {"error": "Already a Billionaire."}

    costs = NET_WORTH_COSTS[next_nw]

    # 1. Money Gate
    if player.corporate_funds < costs["money"]:
        return {"error": f"Insufficient funds. Need ${costs['money']}."}

    # 2. Reputation Gate (The 'Sufficient Reputation' check)
    # If cost is 2, player must have at least -1 reputation to pay it and land at -3
    if (player.reputation - costs["reputation"]) < -3:
        return {"error": f"Reputation too low. Cannot drop below -3."}

    # 3. Execute Upgrade
    player.corporate_funds -= costs["money"]
    player.reputation -= costs["reputation"]
    player.net_worth_level = next_nw

    # TODO: add handling for VP tokens.

    # Update Income (Subsidies are worth more now)
    update_player_income(player)

    db.commit()
    return {
        "action": "net_worth_increased",
        "new_level": player.net_worth_level,
        "new_reputation": player.reputation,
        "new_income": player.income
    }


def recruit_worker(db: Session, player_id: int, target_action: str):
    player = db.get(Player, player_id)
    next_worker_num = player.total_workers + 1

    if next_worker_num > 8:
        return {"error": "Maximum tech workers (8) already reached."}

    # 1. Check Costs and Net Worth
    tier = RECRUIT_COSTS[next_worker_num]
    if player.corporate_funds < tier["money"]:
        return {"error": f"Need ${tier['money']} to recruit worker #{next_worker_num}."}

    if player.net_worth_level < tier["min_nw"]:
        nw_name = ["Startup", "Millionaire", "Billionaire"][tier["min_nw"]]
        return {"error": f"Must be at least a {nw_name} to recruit this worker."}

    # 2. Execute Purchase
    player.corporate_funds -= tier["money"]
    player.total_workers = next_worker_num

    # 3. Immediate Placement
    # We add this worker to the quarterly strategy mid-execution
    new_placement = WorkerPlacement(
        game_id=player.game_id,
        player_id=player_id,
        worker_number=next_worker_num,
        action_type=target_action
    )
    db.add(new_placement)
    db.commit()

    return {
        "action": "worker_recruited",
        "new_total": player.total_workers,
        "placed_on": target_action,
        "remaining_funds": player.corporate_funds
    }


def execute_marketing(db: Session, player_id: int):
    player = db.get(Player, player_id)
    bonus = MARKETING_BONUSES.get(player.net_worth_level)

    # Apply Reputation (Capped at 10)
    player.reputation = min(10, player.reputation + bonus["reputation"])

    # Apply Power (Capped at 40 per your earlier update)
    player.power = min(40, player.power + bonus["power"])

    # Income might change if power increased
    update_player_income(player)

    db.commit()
    return {
        "action": "marketing_resolved",
        "new_reputation": player.reputation,
        "new_power": player.power,
        "new_income": player.income
    }


def execute_raise_funds_sequence(db: Session, player_id: int, chunks: list[int]):
    """
    Performs the Raise Funds action. Allows for taking that action multiple times in a row.
    chunks: A list of worker counts for each 'sub-action'.
    Example: [1, 3] means one 1-worker action then one 3-worker action. This allows players to take this action multiple
        times in a row during their turn.
    """
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        return {"error": "Player not found"}

    summary = []

    for worker_count in chunks:
        if worker_count < 1:
            continue

        # 1. Siphon phase: Move Corporate -> Personal
        amount_siphoned = player.corporate_funds
        player.personal_funds += amount_siphoned
        player.corporate_funds = 0

        # 2. Determine Cap based on worker group size
        if worker_count == 1:
            cap = 8
        elif worker_count == 2:
            cap = 19
        else:  # 3 or more workers
            cap = 39

        # 3. Draw Income (clamped by cap and rules max of 39)
        income_to_draw = min(player.income, cap)
        player.corporate_funds = income_to_draw

        summary.append({
            "workers_in_chunk": worker_count,
            "siphoned": amount_siphoned,
            "drawn": income_to_draw
        })

    db.commit()
    return {
        "action": "raise_funds_resolved",
        "player_id": player_id,
        "sequence_results": summary,
        "final_corporate": player.corporate_funds,
        "final_personal": player.personal_funds
    }


def update_player_income(player: Player):
    # Net Worth Multipliers: Startup=0, Millionaire=1, Billionaire=2
    multiplier = player.net_worth_level

    player.income = player.power + (player.subsidy_tokens * multiplier)

    # Income caps at $39. Any additional income is used up in antitrust lawsuits with the EU.
    if player.income > 39:
        player.income = 39


def place_worker(db: Session, player_id: int, worker_number: int, action_type: str):
    player = db.get(Player, player_id)

    # 1. Validation: Does player own this worker?
    if worker_number > player.total_workers:
        return {"error": f"Player only has {player.total_workers} workers."}

    # 2. Upsert: Update if exists, otherwise create
    placement = db.query(WorkerPlacement).filter(
        WorkerPlacement.player_id == player_id,
        WorkerPlacement.worker_number == worker_number,
        WorkerPlacement.game_id == player.game_id
    ).first()

    if placement:
        placement.action_type = action_type
    else:
        placement = WorkerPlacement(
            game_id=player.game_id,
            player_id=player_id,
            worker_number=worker_number,
            action_type=action_type
        )
        db.add(placement)

    db.commit()
    return {"action": "worker_placed", "worker_number": worker_number, "slot": action_type}


def execute_action(db: Session, player_id: int, action_type: str, worker_count: int = 1):
    """
    The central hub for routing worker actions to their specific logic.
    worker_count: The number of workers assigned to this specific action slot.
    """
    if action_type == "raise_funds":
        # Raise funds already accepts a list (chunks)
        return execute_raise_funds_sequence(db, player_id, [worker_count])

    elif action_type == "train_model":
        # For training, we check if the worker_count meets the tech requirements
        return train_model(db, player_id, worker_count)

    elif action_type == "buy_chips":
        return buy_chips(db, player_id)

    elif action_type == "recruit":
        # Recruitment requires a target for the new worker
        # This will likely be passed from the frontend/API
        return recruit_worker(db, player_id, target_action="marketing")

        # Add other actions (scale_presence, etc.) as we finalize them
    return {"error": "Action type not recognized"}


def get_sorted_players(players: list[Player], p1_index: int) -> list[Player]:
    """
    Returns a list of players sorted clockwise starting from p1_index.
    """
    num_players = len(players)
    # Use a list comprehension with the modulo trick for a cleaner look
    # We sort the original list by player_order first to ensure indexing matches
    players_by_order = sorted(players, key=lambda x: x.player_order)

    return [players_by_order[(p1_index + i) % num_players] for i in range(num_players)]


def resolve_entire_round(db: Session, game_id: int):
    game = db.get(Game, game_id)
    players = db.query(Player).filter(Player.game_id == game_id).all()
    sorted_players = get_sorted_players(players, game.p1_token_index)

    for player in sorted_players:
        resolved_worker_numbers = set()

        while True:
            p = db.query(WorkerPlacement).filter(
                WorkerPlacement.player_id == player.id,
                WorkerPlacement.worker_number.notin_(resolved_worker_numbers)
            ).order_by(WorkerPlacement.worker_number.asc()).first()

            if not p:
                break

            # CORRECTED: Only group workers with the SAME worker_number
            # (In case the UI/Rules allow stacking multiple workers on beat #1)
            worker_group = db.query(WorkerPlacement).filter(
                WorkerPlacement.player_id == player.id,
                WorkerPlacement.worker_number == p.worker_number
            ).all()

            # Dispatch the action for this specific worker number/beat
            execute_action(db, player.id, p.action_type, len(worker_group))

            for worker in worker_group:
                resolved_worker_numbers.add(worker.worker_number)

        # CLEANUP: Reset pending workers after the player's full strategy resolves
        player.pending_train_workers = 0

    # Rotate P1 Token & Clear Board
    game.p1_token_index = (game.p1_token_index + 1) % len(players)
    db.query(WorkerPlacement).filter(WorkerPlacement.game_id == game_id).delete()
    db.commit()

    return {"action": "round_resolved", "new_p1_index": game.p1_token_index}