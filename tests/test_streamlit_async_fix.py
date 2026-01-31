import pytest
import streamlit as st
from unittest.mock import patch, MagicMock
import asyncio
from streamlit_ui import StreamLitUi, schedule, run_in_loop


@pytest.fixture
def mock_streamlit():
    """Mock streamlit session state and functions."""
    with (
        patch("streamlit.session_state", {}),
        patch("streamlit.set_page_config"),
        patch("streamlit.title"),
        patch("streamlit.chat_message"),
        patch("streamlit.markdown"),
        patch("streamlit.chat_input", return_value="test message"),
        patch("streamlit.write"),
    ):
        yield


def test_schedule_function(mock_streamlit):
    """Test that schedule function works with a running event loop."""
    # Setup session state with loop
    st.session_state["loop"] = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state["loop"])

    # Start loop in thread
    import threading

    def run_loop():
        st.session_state["loop"].run_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()

    # Test schedule function
    async def test_coro():
        return "test result"

    future = schedule(test_coro())
    result = future.result(timeout=5)
    assert result == "test result"


def test_run_in_loop_function(mock_streamlit):
    """Test that run_in_loop function works."""
    # Setup session state with loop
    st.session_state["loop"] = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state["loop"])

    # Start loop in thread
    import threading

    def run_loop():
        st.session_state["loop"].run_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()

    # Test run_in_loop function
    async def test_coro():
        return "test result"

    result = run_in_loop(test_coro())
    assert result == "test result"


def test_streamlit_ui_init(mock_streamlit):
    """Test that StreamLitUi can be initialized without errors."""
    with (
        patch("dotenv.load_dotenv"),
        patch("src.init_db.init_db"),
        patch("src.rbac.enforcer.get_enforcer") as mock_enforcer,
        patch("src.registry.register_systems") as mock_register,
        patch("src.runtime.get_runtime") as mock_runtime,
    ):
        # Mock the enforcer
        mock_enforcer_instance = MagicMock()
        mock_enforcer.return_value = mock_enforcer_instance

        # Mock register_systems as async function
        async def async_register():
            pass

        mock_register.return_value = async_register()

        # Mock runtime
        mock_runtime_instance = MagicMock()
        mock_runtime.return_value = mock_runtime_instance

        # Create UI - should not raise RuntimeError
        ui = StreamLitUi()
        ui.init()

        # Verify initialization happened
        assert "initialized" in st.session_state
        assert st.session_state["initialized"] is True
        assert "loop" in st.session_state
        assert "ui" in st.session_state


def test_streamlit_ui_no_double_initialization(mock_streamlit):
    """Test that StreamLitUi doesn't initialize twice."""
    with (
        patch("dotenv.load_dotenv") as mock_dotenv,
        patch("src.init_db.init_db") as mock_init_db,
        patch("src.rbac.enforcer.get_enforcer") as mock_enforcer,
        patch("src.registry.register_systems") as mock_register,
        patch("src.runtime.get_runtime") as mock_runtime,
    ):
        # Mock the enforcer
        mock_enforcer_instance = MagicMock()
        mock_enforcer.return_value = mock_enforcer_instance

        # Mock register_systems as async function
        async def async_register():
            pass

        mock_register.return_value = async_register()

        # Mock runtime
        mock_runtime_instance = MagicMock()
        mock_runtime.return_value = mock_runtime_instance

        # Set up session state as if already initialized
        st.session_state["loop"] = asyncio.new_event_loop()
        st.session_state["initialized"] = True
        st.session_state["ui"] = "existing_ui"

        # Create UI - should not reinitialize
        ui = StreamLitUi()
        ui.init()

        # Verify no reinitialization happened
        mock_dotenv.assert_not_called()
        mock_init_db.assert_not_called()
        mock_enforcer_instance.clear_policy.assert_not_called()
