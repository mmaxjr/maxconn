import pytest
from tests.integration.ssh_server import start_ssh_server
from tests.integration.telnet_server import start_telnet_server


@pytest.fixture
def telnet_server():
    handle = start_telnet_server()
    yield handle
    handle.stop()


@pytest.fixture
def ssh_server():
    handle = start_ssh_server()
    yield handle
    handle.stop()
