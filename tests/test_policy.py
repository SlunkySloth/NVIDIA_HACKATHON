import pytest
from replaylab.models.policy import validate_test


@pytest.mark.parametrize("source", [
    "import os\ndef test_incident(client):\n    assert True\n",
    "def test_incident(client):\n    client.get('https://example.com')\n    assert True\n",
    "def test_incident(client):\n    client = 1\n    assert True\n",
    "def test_incident(client):\n    response = client.get('/state')\n    assert response.__dict__\n",
    "def test_incident(client):\n    for value in [1]:\n        assert value\n",
    "def test_incident(client):\n    response = client.get('/state')\n",
])
def test_generated_regressions_cannot_change_execution_policy(source):
    with pytest.raises(ValueError):
        validate_test(source)
