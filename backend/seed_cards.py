
from sqlalchemy.orm import Session
from backend.models import CardDetails, Component
from backend.enums import CardCategory, ZoneType
from backend.database import SessionLocal

INFLUENCE_CARDS = [
    {
        "title": "Build a Fancy Schmancy HQ",
        "description": "+2 Reputation.\n+2 Power.",
        "requirements": "**Requirements**:\nPresence in at least 2 Regions.",
        "cost": 1,
        "qty": 4,
        "image": "z_fancy_hq.png", # Using short name if exists, else match title
        "effect_slug": "build_hq"
    },
    {
        "title": "Good Ol' Corporate Espionage",
        "description": "When a Competitor with shared presence increases their Model Version:\nStartup/Millionaire: +1 Power. \nBillionaire: +2 Power.",
        "requirements": "**Requirements**:\nModel Version is at least 3.",
        "cost": 0,
        "qty": 3,
        "image": "good_ol_corporate_espionage.png",
        "effect_slug": "corporate_espionage"
    },
    {
        "title": "Defense Contract",
        "description": "If Model Version is less than 5:\nStartup: +1 Power\nMillionaire: +2 Power\nBillionaire: +3 Power",
        "requirements": "**Requirements**:\nModel Version is less than 5.",
        "cost": 1,
        "qty": 3,
        "image": "defense_contract.png",
        "effect_slug": "defense_contract"
    },
    {
        "title": "Intern Volunteer Program",
        "description": "+2 Reputation. \nOnce played, this card cannot be discarded.",
        "requirements": "**Requirements**:\nPresence in at least 2 Regions.",
        "cost": 1,
        "qty": 4,
        "image": "intern_volunteer_program.png",
        "effect_slug": "intern_program"
    },
    {
        "title": "Management Restructuring",
        "description": "You may sell up to 3 power for $5 per power.",
        "requirements": "**Requirements**:\nNone.",
        "cost": 1,
        "qty": 2,
        "image": "management_restructuring.png",
        "effect_slug": "management_restructuring"
    },
    {
        "title": "Influencer Marketing",
        "description": "Startup: +$6\nMillionaire: +$8\nBillionaire: +$10",
        "requirements": "**Requirements**:\nNone.",
        "cost": 1,
        "qty": 4,
        "image": "influencer_marketing.png",
        "effect_slug": "influencer_marketing"
    },
    {
        "title": "Greenwashed Carbon Offsets",
        "description": "+1 Reputation for each Subsidy Token you have.",
        "requirements": "**Requirements**:\nNone.",
        "cost": 1,
        "qty": 4,
        "image": "greenwashed_carbon_offsets.png",
        "effect_slug": "carbon_offsets"
    },
    {
        "title": "Celebrity Sponsor World Tour",
        "description": "Increase Presence to 2 Regions, paying only the price of the more expensive Region.",
        "requirements": "**Requirements**:\nNet Worth Limits Apply.",
        "cost": 1,
        "qty": 4,
        "image": "celebrity_sponsor_world_tour.png",
        "effect_slug": "celebrity_tour"
    },
    {
        "title": "Sponsor Free Wifi",
        "description": "You may pay $1 to gain:\nStartup:  +3 Reputation.\nMillionaire: +2 Reputation.\nBillionaire: +1 Reputation.",
        "requirements": "**Requirements**:\nNone.",
        "cost": 0,
        "qty": 3,
        "image": "sponsor_free_wifi.png",
        "effect_slug": "free_wifi"
    },
    {
        "title": "Debt Fueled Market Expansion",
        "description": "Pay $4 less on all Scale Presence actions this round.",
        "requirements": "**Requirements**:\nPresence in at least 5 Regions.",
        "cost": 1,
        "qty": 5,
        "image": "debt_fueled_market_expansion.png",
        "effect_slug": "debt_expansion"
    },
    {
        "title": "Bribe the UN",
        "description": "+1 Power per Region with Presence.",
        "requirements": "**Requirements**:\nPresence in at most 5 Regions.",
        "cost": 1,
        "qty": 3,
        "image": "bribe_the_un.png", # bribe_un.png in sheet, check implementation
        "effect_slug": "bribe_un"
    },
    {
        "title": "Hire an AI Ethicist",
        "description": "+1 Reputation for every Region where competitors have Presence and you do not.",
        "requirements": "**Requirement**: \nNone.",
        "cost": 1,
        "qty": 3,
        "image": "hire_an_ai_ethicist.png",
        "effect_slug": "hire_ethicist"
    },
    {
        "title": "CEO Goes on Manosphere Podcast Tour",
        "description": "Increase your Power up to +3, paying $1 per Power.",
        "requirements": "**Requirements**: \nNone.",
        "cost": 1,
        "qty": 3,
        "image": "ceo_goes_on_manosphere_podcast_tour.png",
        "effect_slug": "podcast_tour"
    },
    {
        "title": "Make \"We Care About Your Community\" Ads, Globally",
        "description": "+1 Reputation for every Region where you have Presence.",
        "requirements": "**Requirements**:\nNone.",
        "cost": 1,
        "qty": 4,
        "image": "make_we_care_about_your_community_ads_globally.png",
        "effect_slug": "community_ads"
    },
    {
        "title": "Hire a Lobbyist",
        "description": "Startup: +1 Power.\nMillionaire: +2 Power.\nBillionaire: +3 Power. ",
        "requirements": "**Requirements**:\nNone.",
        "cost": 1,
        "qty": 4,
        "image": "hire_a_lobbyist.png",
        "effect_slug": "hire_lobbyist"
    },
    {
        "title": "Court an Autocrat",
        "description": "+3 Power.\n-1 Reputation for each Region where you have Presence.",
        "requirements": "**Requirements**:\nReputation is at least 1.",
        "cost": 0,
        "qty": 2,
        "image": "court_an_autocrat.png",
        "effect_slug": "court_autocrat"
    },
    {
        "title": "Layoffs!",
        "description": "+$3 per Tech Worker you have.\n-1 Tech Worker.",
        "requirements": "**Requirements**:\nNone.",
        "cost": 1,
        "qty": 3,
        "image": "layoffs.png",
        "effect_slug": "layoffs"
    },
    {
        "title": "Sign with a VC Investor",
        "description": "Startup: +$4\nMillionaire: +$6\nBillionaire: + $8",
        "requirements": "**Requirements**:\nLess than $10 in your Corporate Funds.",
        "cost": 1,
        "qty": 3,
        "image": "sign_with_a_vc_investor.png",
        "effect_slug": "vc_investor"
    },
    {
        "title": "Collaborate with a University",
        "description": "+2 Reputation\n+1 Power\n+ $5",
        "requirements": "**Requirements**:\nNone",
        "cost": 2,
        "qty": 4,
        "image": "collaborate_with_a_university.png",
        "effect_slug": "university_collab"
    }
]

def seed_influence_cards(db: Session, game_id: int):
    """Seed Influence Cards into the database."""
    print("Seeding Influence Cards...")
    
    # 1. Clear existing influence cards for this game?? 
    # Or just ensure CardDetails exist. 
    # For now, let's update/create CardDetails.
    
    for card_data in INFLUENCE_CARDS:
        # Check if details exist
        details = db.query(CardDetails).filter_by(name=card_data["title"]).first()
        if not details:
            details = CardDetails(
                name=card_data["title"],
                description=card_data["description"],
                requirements=card_data["requirements"],
                cost=card_data["cost"],
                qty=str(card_data["qty"]),
                deck=CardCategory.INFLUENCE.value,
                effect_slug=card_data["effect_slug"],
                image_file=f"influence_cards/{card_data['image']}",
                is_effect=True # Most influence cards are effects. Setup as effects for now.
            )
            db.add(details)
            db.commit()
            print(f"Created CardDetails: {details.name}")
        else:
             # Update if exists (e.g. schema change)
            details.description = card_data["description"]
            details.requirements = card_data["requirements"]
            details.image_file = f"influence_cards/{card_data['image']}"
            details.cost = card_data["cost"]
            db.commit()

        # 2. Create Instances for the Game
        # Check if deck is already populated? 
        # Assuming fresh game seed usage.
        
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
                    sub_type=CardCategory.INFLUENCE.value,
                    zone=ZoneType.INFLUENCE_DECK.value,
                    is_face_up=False
                )
                db.add(comp)
            db.commit()
            print(f"Added {needed} copies of {details.name} to deck.")
            
if __name__ == "__main__":
    db = SessionLocal()
    # Assuming valid game_id constraint, usually 1 for dev.
    # We might need to handle game creation if totally empty.
    # For dev seeding, let's assume game 1 exists.
    try:
        seed_influence_cards(db, 1)
    finally:
        db.close()
