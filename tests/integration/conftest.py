import pytest
from tests.integration.telnet_server import start_telnet_server


@pytest.fixture
def telnet_server():
    handle = start_telnet_server()
    yield handle
    handle.stop()
