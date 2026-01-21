from flask import Flask, request
from flask_socketio import SocketIO, emit
from backend.database import SessionLocal
from backend.game_engine import draw_card, play_card
from backend.enums import ZoneType

app = Flask(__name__)
# cors_allowed_origins="*" is essential for local development
# so your frontend can talk to your backend.
socketio = SocketIO(app, cors_allowed_origins="*")


@socketio.on("connect")
def handle_connect():
    print(f"Client connected: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")


@socketio.on("draw_card_request")
def handle_draw_card(data):
    """
    Client sends: {'player_id': 1, 'deck_type': 'research_deck'}
    """
    db = SessionLocal()
    try:
        player_id = data.get("player_id")
        deck_type_str = data.get("deck_type")

        # Convert string back to our Enum
        deck_enum = ZoneType(deck_type_str)

        result = draw_card(db, player_id, deck_enum)

        if "error" in result:
            emit("error_notification", result, room=request.sid)
        else:
            # BROADCAST: Tell EVERYONE that a card was moved
            # This is the "Automated Movement" trigger
            socketio.emit("state_updated", result)
            print(f"Broadcasted draw: {result}")

    finally:
        db.close()


@socketio.on("play_card_request")
def handle_play_card(data):
    """
    Client sends: {'player_id': 1, 'card_id': 5, 'target_slot': 2}
    """
    db = SessionLocal()
    try:
        result = play_card(
            db, data.get("player_id"), data.get("card_id"), data.get("target_slot")
        )

        if "error" in result:
            emit("error_notification", result, room=request.sid)
        else:
            socketio.emit("state_updated", result)
            print(f"Broadcasted play: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    # TODO: Use eventlet or gevent for better production performance later,
    # but this works great for dev.
    socketio.run(app, debug=True, port=5000)
