import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from duchess.database import Base
from duchess.engine import ChessEngine
import duchess.models  # noqa: F401


@pytest.fixture(scope="session")
def engine():
    eng = ChessEngine()
    yield eng
    eng.close()


@pytest.fixture(scope="function")
def db_session():
    db_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=db_engine)
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=db_engine)
