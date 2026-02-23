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


@pytest.fixture(autouse=True)
def mock_lichess_api_globally(request):
    """Prevent the opening explorer from spawning network threads during GUI tests.
    We skip this mock for test_opening_explorer.py which tests the client directly."""
    if "test_opening_explorer" in request.module.__name__:
        yield
        return
    
    from unittest.mock import patch
    with patch("duchess.gui.opening_explorer.OpeningExplorerWidget.update_position"):
        yield

@pytest.fixture(autouse=True)
def cleanup_engine_workers():
    """Centrally solve thread-related Python aborts by ensuring all EngineWorkers are joined before test teardown."""
    from duchess.gui.worker import EngineWorker
    EngineWorker._active_workers = getattr(EngineWorker, "_active_workers", [])
    yield
    for worker in list(EngineWorker._active_workers):
        try:
            if worker.isRunning():
                worker.wait(3000)
        except RuntimeError:
            pass
    EngineWorker._active_workers.clear()
