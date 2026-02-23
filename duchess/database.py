# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/duchess_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
