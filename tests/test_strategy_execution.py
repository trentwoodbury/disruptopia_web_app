import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import Player, WorkerPlacement, Game

client = TestClient(app)

def test_full_quarterly_strategy_flow(db_session):
    # 1. Setup Initial State
    # P1 starts with 3 workers, 0 rep, $3 (from seed)
    
    # Place P1 Worker 1 on Marketing
    client.post("/actions/place-worker", json={
        "player_id": 1, "game_id": 1, "worker_ids": [1], "action_type": "marketing"
    })
    # Place P1 Worker 2 on Buy Chips
    client.post("/actions/place-worker", json={
        "player_id": 1, "game_id": 1, "worker_ids": [2], "action_type": "buy_chips"
    })
    
    # Place P2 Worker 1 on Marketing
    client.post("/actions/place-worker", json={
        "player_id": 2, "game_id": 1, "worker_ids": [1], "action_type": "marketing"
    })

    # 2. Execute Step-by-Step Resolution
    # Resolve P1 Marketing
    resp = client.post("/actions/execute/marketing?player_id=1")
    assert resp.status_code == 200
    
    p1 = db_session.get(Player, 1)
    db_session.refresh(p1)
    # Marketing at Startup level adds 3 Reputation
    assert p1.reputation == 3 

    # Resolve P1 Buy Chips
    resp = client.post("/actions/execute/buy-chips?player_id=1")
    assert resp.status_code == 200
    db_session.refresh(p1)
    assert p1.compute_level == 2 
    # Cost $2, started with $3 -> remains $1
    assert p1.corporate_funds == 1

    # Take P2 Marketing
    resp = client.post("/actions/execute/marketing?player_id=2")
    assert resp.status_code == 200
    p2 = db_session.get(Player, 2)
    db_session.refresh(p2)
    assert p2.reputation == 3

    # 3. Finish Round
    resp = client.post("/game/1/finish-round")
    assert resp.status_code == 200
    
    # Verify cleanup
    assert db_session.query(WorkerPlacement).count() == 0
    game = db_session.get(Game, 1)
    assert game.p1_token_index == 1 # Rotated

def test_recruit_and_immediate_resolution(db_session):
    # P1 starts with 3 workers
    client.post("/actions/place-worker", json={
        "player_id": 1, "game_id": 1, "worker_ids": [1], "action_type": "recruit"
    })
    
    resp = client.post("/actions/execute/recruit?player_id=1&target_action=marketing")
    assert resp.status_code == 200
    
    p1 = db_session.get(Player, 1)
    db_session.refresh(p1)
    assert p1.total_workers == 4 # 3 initial + 1 recruited
    
    new_placement = db_session.query(WorkerPlacement).filter_by(player_id=1, action_type="marketing").first()
    assert new_placement is not None
    assert new_placement.worker_number == 4

def test_raise_funds_grouping(db_session):
    # P1 starts with $3. Income 3. 
    # Place 2 workers on Raise Funds
    client.post("/actions/place-worker", json={
        "player_id": 1, "game_id": 1, "worker_ids": [1], "action_type": "raise_funds"
    })
    client.post("/actions/place-worker", json={
        "player_id": 1, "game_id": 1, "worker_ids": [2], "action_type": "raise_funds"
    })
    
    resp = client.post("/actions/execute/raise-funds", json={
        "player_id": 1,
        "chunks": [1, 2]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sequence"]) == 2
    # Sequence 0: Siphons $3, draws income (capped at 8 for 1 worker).
    # Since income is 3, draws 3.
    assert data["sequence"][0]["siphoned"] == 3
    assert data["sequence"][0]["drawn"] == 3
