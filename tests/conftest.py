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
def mock_engine_start_globally(request):
    """Centrally mock EngineManager.start_multipv to prevent runaway threads during tests.
    Tests that actually want to test the engine (like test_gui_main_window.py or test_worker.py)
    should explicitly unmock or just let it be, but since we are mocking it globally, we only
    skip the mock for tests that we know test the engine directly.
    """
    if "test_gui_main_window" in request.module.__name__ or "test_worker" in request.module.__name__:
        yield
        return
        
    from unittest.mock import patch
    with patch("duchess.gui.engine_manager.EngineManager.start_multipv"):
        yield
