from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from duchess.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=True)
    whatsapp = Column(String, unique=True, nullable=True)

    games_as_white = relationship(
        "Game", foreign_keys="Game.white_player_id", back_populates="white_player"
    )
    games_as_black = relationship(
        "Game", foreign_keys="Game.black_player_id", back_populates="black_player"
    )


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    white_player_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    black_player_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fen = Column(
        String,
        nullable=False,
        default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )
    pgn = Column(Text, nullable=True, default="")
    status = Column(String, nullable=False, default="active")

    white_player = relationship(
        "User", foreign_keys=[white_player_id], back_populates="games_as_white"
    )
    black_player = relationship(
        "User", foreign_keys=[black_player_id], back_populates="games_as_black"
    )
    moves = relationship("Move", back_populates="game", order_by="Move.id")


class Move(Base):
    __tablename__ = "moves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    uci = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    game = relationship("Game", back_populates="moves")


class MasterGame(Base):
    __tablename__ = "master_games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event = Column(String, index=True)
    date = Column(String)
    white = Column(String, index=True, nullable=False)
    black = Column(String, index=True, nullable=False)
    result = Column(String, index=True)
    white_elo = Column(Integer)
    black_elo = Column(Integer)
    eco = Column(String, index=True)
    
    # The full raw text of the moves (e.g. "1. e4 e5 ...")
    move_text = Column(Text, nullable=False)

    # Whether this game should be used for NNUE training data generation.
    # True by default for selfplay-generated games, False for imported PGNs.
    training_use = Column(Boolean, nullable=False, default=False, server_default="false")
