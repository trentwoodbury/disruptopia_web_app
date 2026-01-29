from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Dict

from starlette.middleware.cors import CORSMiddleware

from backend.database import SessionLocal
from backend import game_engine, schemas, models


class ConnectionManager:
    def __init__(self):
        # Stores active websocket connections
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Sends a JSON message to all connected players."""
        for connection in self.active_connections:
            await connection.send_json(message)


manager = ConnectionManager()
app = FastAPI(title="Disruptopia API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for MVP testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: int):
    await manager.connect(websocket)
    try:
        while True:
            # We keep the connection alive.
            # Most logic happens via POST, but we can receive chat/pings here.
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


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


@app.post("/actions/place-worker")
async def place_worker(req: schemas.ActionRequest, db: Session = Depends(get_db)):
    # 1. Validation: Ensure at least one worker was sent
    if not req.worker_ids:
        raise HTTPException(status_code=400, detail="No worker IDs provided.")

    # 2. Extract the first worker for the engine (as it handles one-by-one currently)
    primary_worker_id = req.worker_ids[0]

    # 3. Call the engine logic
    result = game_engine.place_worker(
        db,
        player_id=req.player_id,
        worker_number=primary_worker_id,
        action_type=req.action_type,
    )

    # 4. Handle errors from the engine
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # 5. Broadcast the update to all connected players (refreshing the frontend)
    # Note: We need a game_id here. If ActionRequest doesn't have it,
    # we can fetch it from the player object.
    player = db.get(models.Player, req.player_id)
    await manager.broadcast(
        {
            "type": "WORKER_PLACED",
            "game_id": player.game_id,
            "player_id": req.player_id,
            "worker_ids": req.worker_ids,
            "slot": req.action_type,
        }
    )

    return result


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


@app.get("/game/{game_id}/state")
def get_game_state(game_id: int, db: Session = Depends(get_db)):
    players = db.query(models.Player).filter(models.Player.game_id == game_id).all()

    return {
        "game_id": game_id,
        "players": [
            {
                "id": p.id,
                "name": p.user_name,
                "power": p.power,
                "income": p.income,
                "net_worth": p.net_worth_level,
                "reputation": p.reputation,
                "compute_level": p.compute_level,
                "model_version": p.model_version,
                "total_worker_count": p.total_workers,
                "placed_worker_numbers": [w.worker_number for w in p.worker_placements],
            }
            for p in players
        ],
        "placements": [
            {
                "player_id": pl.player_id,
                "action_type": pl.action_type,
                "worker_number": pl.worker_number,
            }
            for pl in db.query(models.WorkerPlacement)
            .filter(models.WorkerPlacement.game_id == game_id)
            .all()
        ],
    }


# --- Step-by-Step Resolution Endpoints ---

@app.post("/actions/execute/buy-chips")
def execute_buy_chips(player_id: int, db: Session = Depends(get_db)):
    result = game_engine.execute_buy_chips(db, player_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/actions/execute/recruit")
def execute_recruit(player_id: int, target_action: str, db: Session = Depends(get_db)):
    result = game_engine.execute_recruit_worker(db, player_id, target_action)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/actions/execute/train-model")
def execute_train_model(player_id: int, worker_count: int, db: Session = Depends(get_db)):
    result = game_engine.execute_train_model(db, player_id, worker_count)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/actions/execute/marketing")
def execute_marketing(player_id: int, db: Session = Depends(get_db)):
    result = game_engine.execute_marketing(db, player_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/actions/execute/scale-presence")
def execute_scale_presence(player_id: int, region_id: int, db: Session = Depends(get_db)):
    result = game_engine.execute_scale_presence(db, player_id, region_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/actions/execute/increase-net-worth")
def execute_increase_net_worth(player_id: int, db: Session = Depends(get_db)):
    result = game_engine.execute_increase_net_worth(db, player_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/actions/execute/raise-funds")
def execute_raise_funds(req: schemas.RaiseFundsRequest, db: Session = Depends(get_db)):
    # Group consecutive workers into a sequence of chunks
    result = game_engine.execute_raise_funds_sequence(db, req.player_id, req.chunks)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/game/{game_id}/finish-round")
def finish_round(game_id: int, db: Session = Depends(get_db)):
    """Clean up board, rotate P1, and return leaderboard."""
    game = db.get(models.Game, game_id)
    players = db.query(models.Player).filter_by(game_id=game_id).all()
    
    # 1. Rotate P1 token
    game.p1_token_index = (game.p1_token_index + 1) % len(players)
    
    # 2. Clear placements
    db.query(models.WorkerPlacement).filter_by(game_id=game_id).delete()
    
    # 3. Calculate final results
    leaderboard = game_engine.calculate_game_leaderboard(db, game_id)
    db.commit()
    
    return {
        "status": "round_finished",
        "new_p1_index": game.p1_token_index,
        "leaderboard": leaderboard
    }
