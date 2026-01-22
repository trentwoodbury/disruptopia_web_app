from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict

from backend.database import SessionLocal
from backend import game_engine, schemas

app = FastAPI(title="Disruptopia API")


# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"status": "Disruptopia Engine Online"}


@app.post("/game/{game_id}/resolve", tags=["Game Flow"])
def resolve_round(game_id: int, db: Session = Depends(get_db)):
    """Triggers the full quarterly strategy resolution."""
    result = game_engine.resolve_entire_round(db, game_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/actions/place-worker", tags=["Actions"])
def place_worker(req: schemas.ActionRequest, db: Session = Depends(get_db)):
    return game_engine.place_worker(
        db, req.player_id, req.worker_number, req.action_type
    )


@app.post("/actions/play-card", tags=["Actions"])
def play_card(req: schemas.CardPlayRequest, db: Session = Depends(get_db)):
    """Executes playing an action card or slotting an effect card."""
    result = game_engine.play_card(db, req.player_id, req.card_id, req.target_slot)

    # If it's an immediate action card, we apply the effect now
    # (Effect cards remain in their slot for round resolution)
    if (
        result.get("action") == "card_played"
        and "active_effect_card" not in result["new_zone"]
    ):
        effect_result = game_engine.apply_card_effect(db, req.player_id, req.card_id)
        return {**result, "effect_result": effect_result}

    return result


@app.get("/game/{game_id}/leaderboard", response_model=List[Dict])
def get_leaderboard(game_id: int, db: Session = Depends(get_db)):
    """Returns the live VP standings."""
    return game_engine.calculate_game_leaderboard(db, game_id)
