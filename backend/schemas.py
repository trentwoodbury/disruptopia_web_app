from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from backend.enums import ZoneType


class ActionRequest(BaseModel):
    """Generic schema for worker placement actions."""

    player_id: int
    action_type: str
    worker_count: int = 1
    target_region: Optional[int] = None


class CardPlayRequest(BaseModel):
    """Specifically for playing cards from hand."""

    player_id: int
    card_id: int
    target_slot: Optional[int] = None


class RaiseFundsRequest(BaseModel):
    """Handles the unique 'chunking' of workers for income."""

    player_id: int
    chunks: List[int]


class GameStateResponse(BaseModel):
    """The structure of the data sent to the frontend to render the board."""

    game_id: int
    phase: str
    p1_index: int
    leaderboard: List[Dict]
    # TODO: eventually add components and player hands here
