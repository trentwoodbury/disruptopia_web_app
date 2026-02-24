
from sqlalchemy.orm import Session
from backend.models import CardDetails, Component
from backend.enums import CardCategory, ZoneType
from backend.database import SessionLocal

RESEARCH_CARDS = [
    {
        "title": "New GPU Tech",
        "description": "All Model Upgrades cost 1 fewer Tech Workers this round.",
        "requirements": "None.",
        "cost": 1,
        "qty": 4,
        "image": "new_gpu_tech.png",
        "effect_slug": "gpu_tech",
        "is_effect": False # Round effect, but played as Action Card? Wait, description says "this round". 
        # Usually implies it sits in play or is instant with lingering effect. 
        # If "Action Card", it goes to discard. But effect lasts round. 
        # So backend must store state. Hence my `temp_model_cost_worker_reduction`.
        # So it is an Action Card (is_effect=False) that triggers a state change.
    },
    {
        "title": "Microdosing Interns",
        "description": "All cards (excluding Active Effect Cards) cost you 1 fewer Tech Workers this round.",
        "requirements": "None.",
        "cost": 0,
        "qty": 5,
        "image": "microdosing_interns.png",
        "effect_slug": "microdosing_interns",
        "is_effect": False
    },
    {
        "title": "Unethical Data Source",
        "description": "Draw 2 Research Cards. If you draw \"Data Labelling Sweatshop\" discard both cards and -1 reputation. Otherwise, play 1 drawn card for free.\n*Ignores effect from Content Moderation*.",
        "requirements": "Reputation Limits apply.",
        "cost": 0,
        "qty": 4,
        "image": "unethical_data_source.png",
        "effect_slug": "unethical_data",
        "is_effect": False
    },
    {
        "title": "Submit a Whitepaper",
        "description": "Take and keep a Tech Worker for free. It can be used this round.",
        "requirements": "Net Worth Limits apply.",
        "cost": 2,
        "qty": 4,
        "image": "submit_a_whitepaper.png",
        "effect_slug": "whitepaper",
        "is_effect": False
    },
    {
        "title": "Data Labelling Sweatshop",
        "description": "All Model Upgrades cost 2 fewer Tech Workers this Round.\n-2 Reputation.",
        "requirements": "Reputation Limits apply.",
        "cost": 1,
        "qty": 2,
        "image": "data_labelling_sweatshop.png",
        "effect_slug": "sweatshop",
        "is_effect": False
    },
    {
        "title": "Hack a Competitor's Model Parameters",
        "description": "Pay $4 to take the Train Model action.",
        "requirements": "At least 1 Competitor with a higher Model Version.\nNet Worth Limits apply.",
        "cost": 0,
        "qty": 3,
        "image": "hack_a_competitors_model_parameters.png",
        "effect_slug": "hack_competitor_model",
        "is_effect": False
    },
    {
        "title": "Build Recruiting Pipeline",
        "description": "Play the Recruit action twice, paying the price of only the more expensive Tech Worker.",
        "requirements": "Net Worth Limits apply.",
        "cost": 1,
        "qty": 4,
        "image": "build_recruiting_pipeline.png",
        "effect_slug": "recruiting_pipeline",
        "is_effect": True # "Effect Card" in sheet? Wait. "Card Type: Effect Card" in sheet for this one.
        # IF it is an Effect Card, it stays on board? But effect sounds instant "Play... twice".
        # Maybe it stays and provides a permanent buff?
        # Re-reading: "Play the Recruit action twice..." sounds instant. 
        # The sheet says "Disruptopia Misc/Effect Card.png" for background.
        # But effect seems instant. I will treat as Instant Action unless it says "Once per round".
        # "Play... twice" -> Immediate execution. I will ensure it executes and discards.
        # Actually, let's look at others. "Big Compute Energy" -> "Every time... this round". That is temporary buffer.
        # If "Build Recruiting Pipeline" is permanent, it would be "Once per round, you may...".
        # It says "Play...". Imperative. Likely Action. Dictionary says "Effect Card.png".
        # I will flag as Action for logic, but verify if user meant Permanent.
        # Given "pipeline", maybe permanent? "Once per round"?
        # But "Cost 1". If permanent, it's very strong.
        # I'll treat as Instant for now based on wording.
    },
    {
        "title": "Open Source Your Model",
        "description": "+1 Power for every 2 Regions with your Presence.",
        "requirements": "None.",
        "cost": 1,
        "qty": 4,
        "image": "open_source_your_model.png",
        "effect_slug": "open_source",
        "is_effect": False
    },
    {
        "title": "Spaghetti Code Legacy",
        "description": "Recruit a Tech Worker without paying.",
        "requirements": "Net Worth Limits apply.",
        "cost": 1,
        "qty": 3,
        "image": "spaghetti_code_legacy.png",
        "effect_slug": "spaghetti_code",
        "is_effect": True # Sheet says Effect.
    },
    {
        "title": "Some Nerdy Server Optimization Thing",
        "description": "+1 Compute for free.",
        "requirements": "Net Worth Limits apply.",
        "cost": 1,
        "qty": 4,
        "image": "some_nerdy_server_optimization_thing.png",
        "effect_slug": "nerdy_optimization",
        "is_effect": False
    },
    {
        "title": "Big Compute Energy",
        "description": "Every time you increase Compute this round, +2 Power.",
        "requirements": "None.",
        "cost": 0,
        "qty": 4,
        "image": "big_compute_energy.png",
        "effect_slug": "big_compute_energy",
        "is_effect": True # Sheet says Effect. "This round" implies temporary.
    },
    {
        "title": "80 Slide Powerpoint Presented in Monotone",
        "description": "+1 Compute for free.\n-1 Reputation",
        "requirements": "**Requirement**:\nNet Worth Limits apply.\nReputation Limits apply.",
        "cost": 1,
        "qty": 3,
        "image": "80_slide_powerpoint_presented_in_monotone.png",
        "effect_slug": "powerpoint",
        "is_effect": True
    },
    {
        "title": "Burn Out Engineering",
        "description": "+2 Compute for free.\n-1 Tech Worker.",
        "requirements": "Net Worth Limits apply.\nCompute level is at most 4.",
        "cost": 1,
        "qty": 3,
        "image": "burn_out_engineering.png",
        "effect_slug": "burn_out",
        "is_effect": False
    },
    {
        "title": "Hackathon",
        "description": "Pay up to $3 less when increasing your Compute Level this round.",
        "requirements": "None.",
        "cost": 2,
        "qty": 4,
        "image": "hackathon.png",
        "effect_slug": "hackathon",
        "is_effect": False
    },
    {
        "title": "New Model Hype",
        "description": "On your next Train Model action, gain 1 Power per every 1 Region with Presence (instead of every 2).",
        "requirements": "Presence in 7 or fewer Regions.",
        "cost": 1,
        "qty": 4,
        "image": "new_model_hype.png",
        "effect_slug": "model_hype",
        "is_effect": False
    },
    {
        "title": "Piggyback Off Competitors",
        "description": "Whenever a competitor with shared presence increases their Model Version this round, you may pay to increase your Compute Version.",
        "requirements": "Net Worth Limits apply.\nCompute Limits apply.",
        "cost": 0,
        "qty": 3,
        "image": "piggyback_off_competitors.png",
        "effect_slug": "piggyback",
        "is_effect": False
    },
    {
        "title": "Flexible Remote Work Policy",
        "description": "Take a Tech Worker for free. This can be used starting next round.",
        "requirements": "Net Worth Limits apply.",
        "cost": 0,
        "qty": 4,
        "image": "flexible_remote_work_policy.png",
        "effect_slug": "remote_work",
        "is_effect": False
    }
]

def seed_research_cards(db: Session, game_id: int):
    """Seed Research Cards into the database."""
    print("Seeding Research Cards...")
    
    for card_data in RESEARCH_CARDS:
        details = db.query(CardDetails).filter_by(name=card_data["title"]).first()
        if not details:
            details = CardDetails(
                name=card_data["title"],
                description=card_data["description"],
                requirements=card_data["requirements"],
                cost=card_data["cost"],
                qty=str(card_data["qty"]),
                deck=CardCategory.RESEARCH.value,
                effect_slug=card_data["effect_slug"],
                image_file=card_data['image'],
                is_effect=card_data.get("is_effect", False)
            )
            db.add(details)
            db.commit()
            print(f"Created CardDetails: {details.name}")
        else:
            # Update
            details.description = card_data["description"]
            details.requirements = card_data["requirements"]
            details.image_file = card_data['image']
            details.cost = card_data["cost"]
            details.is_effect = card_data.get("is_effect", False)
            db.commit()

        # Seed Components
        count = db.query(Component).filter(
            Component.game_id == game_id, 
            Component.card_details_id == details.id
        ).count()
        
        needed = card_data["qty"] - count
        if needed > 0:
            for _ in range(needed):
                comp = Component(
                    game_id=game_id,
                    card_details_id=details.id,
                    name=f"{details.name}_{count + _}",
                    comp_type="card",
                    sub_type=CardCategory.RESEARCH.value,
                    zone=ZoneType.RESEARCH_DECK.value,
                    is_face_up=False
                )
                db.add(comp)
            db.commit()
            print(f"Added {needed} copies of {details.name} to deck.")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_research_cards(db, 1)
    finally:
        db.close()
