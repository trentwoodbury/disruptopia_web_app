from typing import List, Optional
from sqlalchemy import ForeignKey, String, Integer, Boolean, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    current_turn_index: Mapped[int] = mapped_column(default=0)
    game_phase: Mapped[str] = mapped_column(String(30), default="setup")
    p1_token_index: Mapped[int] = mapped_column(Integer, default=0)
    millionaire_count: Mapped[int] = mapped_column(Integer, default=0)
    billionaire_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    players: Mapped[List["Player"]] = relationship(back_populates="game")
    components: Mapped[List["Component"]] = relationship(back_populates="game")


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    user_name: Mapped[str] = mapped_column(String(50))
    player_order: Mapped[int] = mapped_column(Integer)  # 0 to 4
    is_online: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Resources ---
    corporate_funds: Mapped[int] = mapped_column(Integer, default=0)
    personal_funds: Mapped[int] = mapped_column(Integer, default=0)
    reputation: Mapped[int] = mapped_column(Integer, default=0)  # Range -3 to 10

    # --- Levels ---
    # Net Worth: 0 = Startup, 1 = Millionaire, 2 = Billionaire
    net_worth_level: Mapped[int] = mapped_column(Integer, default=0)
    compute_level: Mapped[int] = mapped_column(Integer, default=1)
    model_version: Mapped[int] = mapped_column(Integer, default=1)  # Range 1 to 7
    presence_count: Mapped[int] = mapped_column(
        Integer, default=1
    )  # Number of Regions with presence

    # --- Tech Workers ---
    total_workers: Mapped[int] = mapped_column(Integer, default=3)  # Starts at 3, max 8
    worker_placements: Mapped[List["WorkerPlacement"]] = relationship(
        back_populates="player"
    )

    # --- Stats (Calculated & Stored for UI) ---
    power: Mapped[int] = mapped_column(Integer, default=0)
    subsidy_tokens: Mapped[int] = mapped_column(Integer, default=0)
    income: Mapped[int] = mapped_column(Integer, default=0)  # Power + Subsidies
    vp: Mapped[int] = mapped_column(
        Integer, default=0
    )  # victory points, for the non-boardgame nerds.

    # Relationships
    game: Mapped["Game"] = relationship(back_populates="players")
    # Link to components owned (like Presence Tokens or Cards)
    components: Mapped[List["Component"]] = relationship()


class CardDetails(Base):
    __tablename__ = "card_details"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    is_effect: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  #  True = Effect Card. False = Action Card.
    qty: Mapped[str] = mapped_column(
        String(20)
    )  # How many of this card are there in the deck?
    cost: Mapped[int] = mapped_column(
        Integer
    )  # How many tech workers must be used to play this card
    deck: Mapped[str] = mapped_column(
        String(50)
    )  # One of the CardCategory Enum values.
    effect_slug: Mapped[str] = mapped_column(String(50), nullable=True)


class Component(Base):
    """
    Represents any physical object: Cards, Tokens, or Board Pieces.
    """

    __tablename__ = "components"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    card_details_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("card_details.id")
    )
    card_details: Mapped[Optional["CardDetails"]] = relationship()

    # Metadata
    name: Mapped[str] = mapped_column(String(100))  # e.g., "Policy_Card_01"
    comp_type: Mapped[str] = mapped_column(String(20))  # "card", "token", "meeple"
    sub_type: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # e.g., "RESEARCH", "INFLUENCE"

    # State & Location
    # 'zone' defines where it is (e.g., 'BOARD', 'DECK', 'HAND_PLAYER_1')
    zone: Mapped[str] = mapped_column(String(30), default="DECK")

    # Coordinates for when it is on the BOARD (using Metric/Float for precision)
    pos_x: Mapped[float] = mapped_column(Float, default=0.0)
    pos_y: Mapped[float] = mapped_column(Float, default=0.0)
    z_index: Mapped[int] = mapped_column(Integer, default=0)

    is_face_up: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("players.id"))

    game: Mapped["Game"] = relationship(back_populates="components")


class WorkerPlacement(Base):
    __tablename__ = "worker_placements"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))

    worker_number: Mapped[int] = mapped_column(Integer)  # 1-8
    # (e.g., 'buy_chips', 'raise_funds', 'recruit')
    action_type: Mapped[str] = mapped_column(String(50))

    player: Mapped["Player"] = relationship(back_populates="worker_placements")


class Presence(Base):
    __tablename__ = "presence"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    region_id: Mapped[int] = mapped_column(Integer)  # 1 through 10


class RegionState(Base):
    __tablename__ = "region_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    region_id: Mapped[int] = mapped_column(Integer)  # 1-10
    subsidy_tokens_remaining: Mapped[int] = mapped_column(Integer)


class ReputationTile(Base):
    __tablename__ = "reputation_tiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    level: Mapped[int] = mapped_column(Integer)  # 0, 1, 2, or 3
    name: Mapped[str] = mapped_column(
        String(50)
    )  # e.g., "Tax Haven" or "Public Darling"
    owner_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=True)
    effect_code: Mapped[str] = mapped_column(
        String(50)
    )  # Internal ID for the bonus logic
