import sys
import os

# Ensure backend acts as module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.database import SessionLocal, engine
from backend.models import Base, Player, CardDetails, Component, WorkerPlacement
from backend.seed import seed_initial_game
from backend.game_engine import resolve_entire_round, place_worker
from backend.card_effects import CARD_EFFECT_REGISTRY

def run_test():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_initial_game()
    
    db = SessionLocal()
    
    player = db.query(Player).first()
    print(f"Player {player.id} workers: {player.total_workers}")
    
    card_detail = CardDetails(name="dummy_action", is_effect=False, qty="1", cost=1, deck="influence", effect_slug="dummy_sabotage")
    db.add(card_detail)
    db.flush()
    
    card = Component(name="dummy_action_1", comp_type="card", sub_type="influence", zone=f"hand_p{player.id}", owner_id=player.id, game_id=player.game_id, card_details_id=card_detail.id)
    db.add(card)
    db.commit()
    
    CARD_EFFECT_REGISTRY["dummy_sabotage"] = lambda db, p_id, c_id: {"success": True, "message": "Dummy effect completed"}
    
    # Give player workers
    player.total_workers = 5
    db.commit()
    
    print("Placing worker...")
    res = place_worker(db, player.id, worker_number=1, action_type="play_card", target_region=None, target_card_id=card.id)
    print("Place worker res:", res)
    
    # check db placement
    pl = db.query(WorkerPlacement).filter_by(player_id=player.id).first()
    print(f"DB placement: {pl.action_type}, target_card: {pl.target_card_id}")
    
    print("Resolving round...")
    resolve_res = resolve_entire_round(db, player.game_id)
    print("Resolve res:", resolve_res)
    
    db.refresh(card)
    print("Card final zone:", card.zone)

if __name__ == '__main__':
    run_test()
