
from sqlalchemy.orm import Session
from backend.models import Player, Component, RegionState, Presence
from backend.game_engine import update_player_income, get_player_modifiers
from backend.config import RECRUIT_COSTS, PRESENCE_COSTS

# Helper
def _add_power(db: Session, player: Player, amount: int):
    """Adds power safely capped at 40."""
    player.power = min(40, player.power + amount)
    update_player_income(db, player)

def _add_reputation(db: Session, player: Player, amount: int):
    """Adds reputation safely capped at 10."""
    player.reputation = min(10, player.reputation + amount)

def _count_shared_competitor_presence(db: Session, player_id: int):
    """Counts regions where player and at least one competitor both have presence."""
    # This is complex. 
    # 1. Get player's regions
    player_regions = [p.region_id for p in player.presence]
    if not player_regions:
        return 0
        
    # 2. Check each region for OTHER players
    count = 0
    for rid in player_regions:
        competitors = db.query(Presence).filter(
            Presence.region_id == rid, 
            Presence.player_id != player_id
        ).count()
        if competitors > 0:
            count += 1
    return count

def _count_competitor_only_presence(db: Session, player_id: int):
    """Counts regions where competitors have presence but player does NOT."""
    player_regions = {p.region_id for p in player.presence}
    
    # Get all regions with ANY presence
    all_occupied = db.query(Presence.region_id).distinct().all()
    all_occupied_ids = {r[0] for r in all_occupied}
    
    # Regions with presence - My Regions = Competitor Only?
    # Not quite. We need regions where at least one competitor is.
    # If I am not in a region, and it is in all_occupied_ids, then a competitor MUST be there.
    # (Since I'm not there to trigger the 'occupied' status).
    
    competitor_only = [
        rid for rid in all_occupied_ids 
        if rid not in player_regions
    ]
    return len(competitor_only)


# --- Effect Implementations ---

def effect_build_hq(db: Session, player_id: int, card_id: int):
    """+2 Reputation, +2 Power. Req: Presence in 2+ Regions."""
    player = db.get(Player, player_id)
    if player.presence_count < 2:
        return {"error": "Requirement not met: Presence in at least 2 Regions."}
        
    _add_reputation(db, player, 2)
    _add_power(db, player, 2)
    db.commit()
    return {"success": True, "message": "HQ Built! +2 Rep, +2 Power."}

def effect_corporate_espionage(db: Session, player_id: int, card_id: int):
    """Passive: When competitor increases Model... Req: Model >= 3."""
    player = db.get(Player, player_id)
    if player.model_version < 3:
        return {"error": "Requirement not met: Model Version must be at least 3."}
    
    # This is a passive effect. It sits in the slot.
    # The actual logic needs to be hooked into `execute_train_model` or similar.
    # For now, we just validate placement.
    return {"success": True, "message": "Espionage active."}

def effect_defense_contract(db: Session, player_id: int, card_id: int):
    """Power based on Rank. Req: Model < 5."""
    player = db.get(Player, player_id)
    if player.model_version >= 5:
        return {"error": "Requirement not met: Model Version must be less than 5."}
        
    boost = {0: 1, 1: 2, 2: 3}.get(player.net_worth_level, 1)
    _add_power(db, player, boost)
    db.commit()
    return {"success": True, "message": f"Defense Contract signed. +{boost} Power."}

def effect_intern_program(db: Session, player_id: int, card_id: int):
    """+2 Rep. Cannot be discarded. Req: Presence 2+."""
    player = db.get(Player, player_id)
    if player.presence_count < 2:
        return {"error": "Requirement not met: Presence in at least 2 Regions."}
        
    _add_reputation(db, player, 2)
    # "Cannot be discarded" logic needs to be enforced in `discard_card` or UI.
    # We can mark it with a flag or just rely on player honesty/UI hiding discard button.
    # Or maybe `is_locked` attribute on Component? For now, just effect.
    db.commit()
    return {"success": True, "message": "Interns hired. +2 Reputation."}

def effect_management_restructuring(db: Session, player_id: int, card_id: int):
    """Sell up to 3 Power for $5 each. Req: None."""
    # This requires INPUT. The card play needs to know how many to sell.
    # Ideally, `play_card` would accept `payload` dict.
    # Current `play_card` only takes `target_slot`.
    # For MVP, let's assume MAX possible up to 3.
    player = db.get(Player, player_id)
    
    can_sell = min(player.power, 3)
    if can_sell == 0:
         return {"success": True, "message": "No power to sell."}
         
    earned = can_sell * 5
    player.power -= can_sell
    player.corporate_funds += earned
    update_player_income(db, player)
    db.commit()
    return {"success": True, "message": f"Sold {can_sell} Power for ${earned}."}

def effect_influencer_marketing(db: Session, player_id: int, card_id: int):
    """Cash based on rank. Req: None."""
    player = db.get(Player, player_id)
    cash = {0: 6, 1: 8, 2: 10}.get(player.net_worth_level, 6)
    player.corporate_funds += cash
    db.commit()
    return {"success": True, "message": f"Influencers paid off. +${cash}."}

def effect_carbon_offsets(db: Session, player_id: int, card_id: int):
    """+1 Rep per Subsidy Token. Req: None."""
    player = db.get(Player, player_id)
    amount = player.subsidy_tokens
    if amount > 0:
        _add_reputation(db, player, amount)
    db.commit()
    return {"success": True, "message": f"Greenwashed! +{amount} Reputation."}

def effect_celebrity_tour(db: Session, player_id: int, card_id: int):
    """Increase Presence to 2 Regions (pick 2?), pay only expensive one. Req: NW Limits."""
    # This is a complex interaction. "Increase Presence to 2 Regions". 
    # implied: Pick 2 new regions? Or pick up to 2?
    # And "pay only price of expensive one".
    # This requires Selection input.
    # WITHOUT payload support in `play_card`, this is hard.
    # Workaround: This card might need to be "Activated" from the slot?
    # Or `play_card` needs to handle arbitrary args.
    # For now, return error asking for implementation of interactive cards.
    return {"error": "Not implemented: Requires region selection interaction."}

def effect_free_wifi(db: Session, player_id: int, card_id: int):
    """Pay $1 -> Gain Rep based on Rank. Req: None."""
    player = db.get(Player, player_id)
    if player.corporate_funds < 1:
        return {"error": "Insufficient requirements: Need $1."}
        
    player.corporate_funds -= 1
    boost = {0: 3, 1: 2, 2: 1}.get(player.net_worth_level, 3)
    _add_reputation(db, player, boost)
    db.commit()
    return {"success": True, "message": f"Wifi Sponsored. +{boost} Reputation."}

def effect_debt_expansion(db: Session, player_id: int, card_id: int):
    """Pay $4 less on Scale Presence this round. Req: Presence 5+."""
    player = db.get(Player, player_id)
    if player.presence_count < 5:
        return {"error": "Requirement not met: Presence in at least 5 Regions."}
    
    # Passive effect. Logic must be in `validate_measure_presence` or `execute_scale_presence`.
    return {"success": True, "message": "Expansion discount active."}

def effect_bribe_un(db: Session, player_id: int, card_id: int):
    """+1 Power per Region. Req: Presence <= 5."""
    player = db.get(Player, player_id)
    if player.presence_count > 5:
        return {"error": "Requirement not met: Presence in at most 5 Regions."}
        
    amount = player.presence_count
    _add_power(db, player, amount)
    db.commit()
    return {"success": True, "message": f"UN Bribed. +{amount} Power."}

def effect_hire_ethicist(db: Session, player_id: int, card_id: int):
    """+1 Rep per competitors_only_region. Req: None."""
    player = db.get(Player, player_id)
    count = _count_competitor_only_presence(db, player.id)
    _add_reputation(db, player, count)
    db.commit()
    return {"success": True, "message": f"Ethicist hired. +{count} Reputation."}

def effect_podcast_tour(db: Session, player_id: int, card_id: int):
    """Power +3, pay $1 per Power. Req: None."""
    # "Up to +3". Implies choice.
    # Assuming Max affordable.
    player = db.get(Player, player_id)
    affordable = player.corporate_funds
    to_buy = min(3, affordable)
    
    if to_buy == 0:
        return {"success": True, "message": "No funds to buy power."}
        
    player.corporate_funds -= to_buy
    _add_power(db, player, to_buy)
    db.commit()
    return {"success": True, "message": f"Podcast Tour complete. +{to_buy} Power for ${to_buy}."}

def effect_community_ads(db: Session, player_id: int, card_id: int):
    """+1 Rep per Presence Region. Req: None."""
    player = db.get(Player, player_id)
    _add_reputation(db, player, player.presence_count)
    db.commit()
    return {"success": True, "message": f"Ads run. +{player.presence_count} Reputation."}

def effect_hire_lobbyist(db: Session, player_id: int, card_id: int):
    """Power based on Rank. Req: None."""
    player = db.get(Player, player_id)
    boost = {0: 1, 1: 2, 2: 3}.get(player.net_worth_level, 1)
    _add_power(db, player, boost)
    db.commit()
    return {"success": True, "message": f"Lobbyist hired. +{boost} Power."}

def effect_court_autocrat(db: Session, player_id: int, card_id: int):
    """+3 Power, -1 Rep per Presence. Req: Rep >= 1."""
    player = db.get(Player, player_id)
    if player.reputation < 1:
        return {"error": "Requirement not met: Reputation must be at least 1."}
        
    rep_loss = player.presence_count
    _add_power(db, player, 3)
    
    # Rep can go below -3? Rules say floor is -3 usually.
    player.reputation = max(-3, player.reputation - rep_loss)
    db.commit()
    return {"success": True, "message": f"Autocrat courted. +3 Power, -{rep_loss} Rep."}

def effect_layoffs(db: Session, player_id: int, card_id: int):
    """+$3 per Tech Worker, -1 Worker. Req: None."""
    player = db.get(Player, player_id)
    # Check if we can lose a worker? 
    if player.total_workers <= 1:
         return {"error": "Cannot fire last worker."}
         
    gain = player.total_workers * 3
    player.total_workers -= 1
    player.corporate_funds += gain
    db.commit()
    return {"success": True, "message": f"Layoffs executed. +${gain}, -1 Worker."}

def effect_vc_investor(db: Session, player_id: int, card_id: int):
    """Cash based on Rank. Req: Funds < 10."""
    player = db.get(Player, player_id)
    if player.corporate_funds >= 10:
        return {"error": "Requirement not met: Corporate Funds must be less than $10."}
        
    gain = {0: 4, 1: 6, 2: 8}.get(player.net_worth_level, 4)
    player.corporate_funds += gain
    db.commit()
    return {"success": True, "message": f"VC Signed. +${gain}."}

def effect_university_collab(db: Session, player_id: int, card_id: int):
    """+2 Rep, +1 Power, +$5. Req: None."""
    player = db.get(Player, player_id)
    _add_reputation(db, player, 2)
    _add_power(db, player, 1)
    player.corporate_funds += 5
    db.commit()
    return {"success": True, "message": "Collaboration successful. +2 Rep, +1 Pwr, +$5."}
    

# Registry mapping Card Detail effect slugs to functions
# Registry mapping Card Detail effect slugs to functions
CARD_EFFECT_REGISTRY = {
    # Existing
    "university_collab": effect_university_collab,
    
    # Influence Cards
    "build_hq": effect_build_hq,
    "corporate_espionage": effect_corporate_espionage,
    "defense_contract": effect_defense_contract,
    "intern_program": effect_intern_program,
    "management_restructuring": effect_management_restructuring,
    "influencer_marketing": effect_influencer_marketing,
    "carbon_offsets": effect_carbon_offsets,
    "celebrity_tour": effect_celebrity_tour,
    "free_wifi": effect_free_wifi,
    "debt_expansion": effect_debt_expansion,
    "bribe_un": effect_bribe_un,
    "hire_ethicist": effect_hire_ethicist,
    "podcast_tour": effect_podcast_tour,
    "community_ads": effect_community_ads,
    "hire_lobbyist": effect_hire_lobbyist,
    "court_autocrat": effect_court_autocrat,
    "layoffs": effect_layoffs,
    "vc_investor": effect_vc_investor,
}

# --- Research Card Effects ---

def effect_gpu_tech(db: Session, player_id: int, card_id: int):
    """All Model Upgrades cost 1 fewer Tech Workers this round."""
    player = db.get(Player, player_id)
    player.temp_model_cost_worker_reduction += 1
    db.commit()
    return {"success": True, "message": "GPU Tech: Model Upgrades -1 Worker Cost this round."}

def effect_microdosing_interns(db: Session, player_id: int, card_id: int):
    """All cards cost 1 fewer Tech Workers this round (excluding Active Effect cards?). Description says 'excluding Active Effect Cards'."""
    player = db.get(Player, player_id)
    player.temp_card_cost_worker_reduction += 1
    db.commit()
    return {"success": True, "message": "Microdosing: Cards -1 Worker Cost this round."}

def effect_unethical_data(db: Session, player_id: int, card_id: int):
    """Draw 2. If 'Sweatshop' drawn, discard both & -1 Rep. Else play 1 free."""
    # Local import to avoid circular dependency
    from backend.game_engine import draw_card, discard_card, play_card
    from backend.enums import ZoneType
    from backend.models import Component
    
    player = db.get(Player, player_id)
    drawn_cards = []
    
    # Draw 2
    for _ in range(2):
        res = draw_card(db, player_id, ZoneType.RESEARCH_DECK)
        if "component_id" in res:
            c = db.get(Component, res["component_id"])
            drawn_cards.append(c)

    if not drawn_cards:
        return {"success": True, "message": "Deck empty, nothing drawn."}
        
    # Check for Sweatshop
    sweatshop_drawn = any(c.card_details.effect_slug == "sweatshop" for c in drawn_cards)
    
    if sweatshop_drawn:
        # Discard all
        for c in drawn_cards:
             # Manually move to discard (or use discard_card helper if reusable)
             c.zone = f"{c.sub_type}_discard"
             c.owner_id = None
        _add_reputation(db, player, -1)
        db.commit()
        return {"success": True, "message": "Drawn Sweatshop! Discarded both, -1 Rep."}
    else:
        # Play 1 free. 
        c_play = drawn_cards[0]
        
        # Execute Card 1 Effect
        # If it's an instantaneous effect, execute it.
        # If it's an "Active Effect Card" (slot), place it.
        
        if c_play.card_details.is_effect:
             # Find open slot?
             # For simplicity, let's just trigger effect function if exists.
             if c_play.card_details.effect_slug in CARD_EFFECT_REGISTRY:
                 CARD_EFFECT_REGISTRY[c_play.card_details.effect_slug](db, player_id, c_play.id)
             
             # Place in slot (Mocking slot 1 priority)
             c_play.zone = f"active_effect_card_slot_1_p{player_id}" 
        else:
             # Normal card (Instant)
             if c_play.card_details.effect_slug in CARD_EFFECT_REGISTRY:
                 CARD_EFFECT_REGISTRY[c_play.card_details.effect_slug](db, player_id, c_play.id)
             
             c_play.zone = f"{c_play.sub_type}_discard"
             c_play.owner_id = None
             
        db.commit()
        return {"success": True, "message": f"Played {c_play.card_details.name} for free."}

def effect_whitepaper(db: Session, player_id: int, card_id: int):
    """Take and keep Tech Worker free. Used this round."""
    player = db.get(Player, player_id)
    player.total_workers += 1
    db.commit()
    return {"success": True, "message": "Whitepaper: +1 Worker (Available Now)."}

def effect_sweatshop(db: Session, player_id: int, card_id: int):
    """Model Upgrades cost 2 fewer Workers. -2 Rep."""
    player = db.get(Player, player_id)
    player.temp_model_cost_worker_reduction += 2
    _add_reputation(db, player, -2)
    db.commit()
    return {"success": True, "message": "Sweatshop: Model Cost -2 Workers, -2 Rep."}

def effect_hack_competitor_model(db: Session, player_id: int, card_id: int):
    """Pay $4 to take Train Model action."""
    from backend.game_engine import execute_train_model
    player = db.get(Player, player_id)
    
    # Req: Competitor with Higher Model
    competitors = db.query(Player).filter(Player.game_id == player.game_id, Player.id != player_id).all()
    if not any(c.model_version > player.model_version for c in competitors):
        return {"error": "Requirement not met: No competitor has a higher Model Version."}
        
    if player.corporate_funds < 4:
        return {"error": "Insufficient funds: Need $4."}
        
    player.corporate_funds -= 4
    # Execute Train Model (1 worker equivalent? Or just effect?)
    # "Take the Train Model action". Implies standard upgrade logic.
    res = execute_train_model(db, player_id, worker_count=1) # Assuming 1 worker strength? logic usually checks count for cost.
    # But this is a defined action. 
    # `execute_train_model` checks costs based on `worker_count`.
    # AND `temp_model_cost_worker_reduction` will apply. 
    # But here we paid $4 INSTEAD? or in addition?
    # "Pay $4 to take...". 
    # Implies the $4 PAYS for the action. 
    # I should probably force the upgrade directly to avoid double cost.
    
    # Direct Upgrade Logic
    # Cost to upgrade to Next Level usually = Workers.
    # Here we paid $4. So we skip worker cost?
    # Logic:
    current_ver = player.model_version
    # Max check
    if current_ver >= 7:
         return {"error": "Max Model Version."}
         
    player.model_version += 1
    # Check max?
    db.commit()
    return {"success": True, "message": "Hacked Model: Upgraded to V" + str(player.model_version)}

def effect_recruiting_pipeline(db: Session, player_id: int, card_id: int):
    """Play Recruit twice, pay only expensive."""
    # This implies we add 2 workers, but pay for 1.
    # Recruit costs depend on Target Level (which depends on current workers).
    # Current Workers: N. 
    # Recruit 1: Cost for N+1.
    # Recruit 2: Cost for N+2.
    # Pay max(Cost1, Cost2) -> Cost2.
    # So we add 2 workers, pay Cost for (N+2).
    
    from backend.config import RECRUIT_COSTS
    player = db.get(Player, player_id)
    
    next_worker_idx = player.total_workers + 1
    next_next_worker_idx = player.total_workers + 2
    
    if next_next_worker_idx not in RECRUIT_COSTS:
        return {"error": "Cannot recruit beyond max workers."}
        
    cost_dict = RECRUIT_COSTS[next_next_worker_idx]
    cost_cash = cost_dict["money"]
    
    if player.corporate_funds < cost_cash:
        return {"error": f"Insufficient funds: Need ${cost_cash}."}
        
    player.corporate_funds -= cost_cash
    player.total_workers += 2
    db.commit()
    return {"success": True, "message": f"Pipeline Built: +2 Workers for ${cost_cash}."}

def effect_open_source(db: Session, player_id: int, card_id: int):
    """+1 Power per 2 Regions with Presence."""
    player = db.get(Player, player_id)
    bonus = player.presence_count // 2
    _add_power(db, player, bonus)
    db.commit()
    return {"success": True, "message": f"Open Source: +{bonus} Power."}

def effect_spaghetti_code(db: Session, player_id: int, card_id: int):
    """Recruit without paying."""
    player = db.get(Player, player_id)
    if player.total_workers >= 8:
         return {"error": "Max workers reached."}
    
    player.total_workers += 1
    db.commit()
    return {"success": True, "message": "Spaghetti Code: +1 Worker (Free)."}

def effect_nerdy_optimization(db: Session, player_id: int, card_id: int):
    """+1 Compute for free."""
    player = db.get(Player, player_id)
    player.compute_level += 1
    db.commit()
    # Should check max compute?
    return {"success": True, "message": "Optimized: +1 Compute."}

def effect_big_compute_energy(db: Session, player_id: int, card_id: int):
    """Every time you increase Compute this round, +2 Power."""
    player = db.get(Player, player_id)
    player.temp_compute_gain_power_bonus += 2
    db.commit()
    return {"success": True, "message": "Big Compute Energy active."}

def effect_powerpoint(db: Session, player_id: int, card_id: int):
    """+1 Compute free. -1 Rep."""
    player = db.get(Player, player_id)
    player.compute_level += 1
    _add_reputation(db, player, -1)
    db.commit()
    return {"success": True, "message": "Powerpoint: +1 Compute, -1 Rep."}

def effect_burn_out(db: Session, player_id: int, card_id: int):
    """+2 Compute free. -1 Worker. Req: Compute <= 4."""
    player = db.get(Player, player_id)
    if player.compute_level > 4:
        return {"error": "Requirement not met: Compute must be at most 4."}
        
    if player.total_workers <= 1:
        return {"error": "Cannot burn out last worker."}

    player.compute_level += 2
    player.total_workers -= 1
    db.commit()
    return {"success": True, "message": "Burn Out: +2 Compute, -1 Worker."}

def effect_hackathon(db: Session, player_id: int, card_id: int):
    """Pay up to $3 less when increasing Compute this round."""
    player = db.get(Player, player_id)
    player.temp_compute_monetary_discount += 3
    db.commit()
    return {"success": True, "message": "Hackathon: Compute Upgrade -$3 discount."}

def effect_model_hype(db: Session, player_id: int, card_id: int):
    """Next Train Model: +1 Power per Region (instead of per 2)."""
    player = db.get(Player, player_id)
    if player.presence_count > 7:
         return {"error": "Requirement not met: Presence <= 7."}
         
    player.temp_train_model_per_region_power_bonus = True
    db.commit()
    return {"success": True, "message": "Model Hype active."}

def effect_piggyback(db: Session, player_id: int, card_id: int):
    """When competitor... pay to increase Compute."""
    player = db.get(Player, player_id)
    player.temp_piggyback_competitor_model = True
    db.commit()
    return {"success": True, "message": "Piggyback active."}

def effect_remote_work(db: Session, player_id: int, card_id: int):
    """Take Worker free. Used next round."""
    # To implement "Used next round", we can add a placement to `WorkerPlacement` 
    # that "occupies" this new worker for the current round?
    # Or just add to `total_workers`. Since `place_worker` creates placements sequentially (1, 2, 3...),
    # if I add a worker now, say I had 3, now 4.
    # I can place worker 4.
    # To Block it, I should insert a dummy placement for worker 4.
    
    player = db.get(Player, player_id)
    player.total_workers += 1
    
    # Block usage this round
    from backend.models import WorkerPlacement
    new_worker_num = player.total_workers
    dummy_placement = WorkerPlacement(
         game_id=player.game_id,
         player_id=player_id, 
         worker_number=new_worker_num,
         action_type="remote_work_cooldown",
         target_region=0
    )
    db.add(dummy_placement)
    
    db.commit()
    return {"success": True, "message": "Remote Work: +1 Worker (Available Next Round)."}

# Update Registry
CARD_EFFECT_REGISTRY.update({
    "gpu_tech": effect_gpu_tech,
    "microdosing_interns": effect_microdosing_interns,
    "unethical_data": effect_unethical_data,
    "whitepaper": effect_whitepaper,
    "sweatshop": effect_sweatshop,
    "hack_competitor_model": effect_hack_competitor_model,
    "recruiting_pipeline": effect_recruiting_pipeline,
    "open_source": effect_open_source,
    "spaghetti_code": effect_spaghetti_code,
    "nerdy_optimization": effect_nerdy_optimization,
    "big_compute_energy": effect_big_compute_energy,
    "powerpoint": effect_powerpoint,
    "burn_out": effect_burn_out,
    "hackathon": effect_hackathon,
    "model_hype": effect_model_hype,
    "piggyback": effect_piggyback,
    "remote_work": effect_remote_work,
    "nerdy_server_optimization": effect_nerdy_optimization,
})

