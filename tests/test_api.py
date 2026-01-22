from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_websocket_broadcast(db_session):
    with client.websocket_connect("/ws/1") as websocket:
        # Update the JSON to use worker_ids as a list
        response = client.post(
            "/actions/place-worker",
            json={
                "player_id": 1,
                "game_id": 1,
                "worker_ids": [1],
                "action_type": "marketing",
            },
        )

        assert response.status_code == 200

        data = websocket.receive_json()
        assert data["type"] == "WORKER_PLACED"
        assert data["worker_ids"] == [1]
        assert data["slot"] == "marketing"
