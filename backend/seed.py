from backend.database import SessionLocal, engine
from backend.models import Base, Game, Player, Component, CardDetails, RegionState
from backend.enums import ZoneType, ComponentType, CardCategory


def seed_regions(db, game_id, player_count):
    tokens_per_region = 1 if player_count <= 3 else 2
    for r_id in range(1, 11):
        region = RegionState(
            game_id=game_id,
            region_id=r_id,
            subsidy_tokens_remaining=tokens_per_region
        )
        db.add(region)
    db.commit()


def seed_initial_game():
    db = SessionLocal()
    try:
        # 1. Create Game & Players
        new_game = Game(game_phase="setup")
        db.add(new_game)
        db.commit()
        db.refresh(new_game)

        p1 = Player(
            user_name="Player One",
            player_order=0,
            game_id=new_game.id,
            power=3,
            income=3,
            corporate_funds=3,
            personal_funds=0,
            total_workers=3,
            reputation=0,
            net_worth_level=0,
            model_version=0,
            compute_level=1,
            presence_count=1,
            subsidy_tokens=0
        )
        p2 = Player(
            user_name="Player Two",
            player_order=1,
            game_id=new_game.id,
            power=3,
            income=3,
            corporate_funds=3,
            personal_funds=0,
            total_workers=3,
            reputation=0,
            net_worth_level=0,
            model_version=0,
            compute_level=1,
            presence_count=1,
            subsidy_tokens=0
        )
        db.add_all([p1, p2])
        db.commit()

        player_count = 2
        seed_regions(db, new_game.id, player_count)

        # 2. Define the Card Library (Definitions)
        # TODO: move to a separate JSON file.
        card_library = [
            {
                "name": "good_ol_corporate_espionage",
                "is_effect": True,
                "qty": 5,
                "cost": 2,
                "deck": CardCategory.INFLUENCE.value
            },
            {
                "name": "unethical_data_source",
                "is_effect": False,
                "qty": 10,
                "cost": 1,
                "deck": CardCategory.RESEARCH.value
            }
        ]

        # 3. Create Definitions and physical Components
        for data in card_library:
            # Create the shared definition
            detail = CardDetails(
                name=data["name"],
                is_effect=data["is_effect"],
                qty=str(data["qty"]), # Matching your String(20) model
                cost=data["cost"],
                deck=data["deck"]
            )
            db.add(detail)
            db.flush() # Get detail.id without committing yet

            # Create the physical cards (Components)
            for i in range(data["qty"]):
                new_card = Component(
                    name=f"{detail.name}_{i+1}", # e.g. unethical_data_source_1
                    comp_type=ComponentType.CARD.value,
                    sub_type=detail.deck, # Match sub_type to the deck category
                    zone=f"{detail.deck}_deck", # e.g. research_deck
                    game_id=new_game.id,
                    card_details_id=detail.id # Link the two tables
                )
                db.add(new_card)

        db.commit()
        print("Database re-seeded successfully with Card Library and Components.")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()