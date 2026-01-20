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

    game: Mapped["Game"] = relationship(back_populates="players")


class Component(Base):
    """
    Represents any physical object: Cards, Tokens, or Board Pieces.
    """
    __tablename__ = "components"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))

    # Metadata
    name: Mapped[str] = mapped_column(String(100))  # e.g., "Policy_Card_01"
    comp_type: Mapped[str] = mapped_column(String(20))  # "card", "token", "meeple"
    sub_type: Mapped[Optional[str]] = mapped_column(String(50))  # e.g., "RESEARCH", "INFLUENCE"

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