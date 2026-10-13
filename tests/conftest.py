import pytest
from fastapi.testclient import TestClient
from replaylab.api.app import create_app
from replaylab.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, api_key="", model="", sandbox_key="", sandbox_url="", sandbox_image="", public_demo=False, secure_cookie=False, run_timeout=90)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
