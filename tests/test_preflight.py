from argparse import Namespace

import pytest
from replaylab.preflight import configuration, doctor


def test_configuration_diagnostics_report_names_without_secret_values(settings):
    settings.api_key = "unit-test-private-placeholder"
    report = configuration(settings)
    assert not report["configured"]
    assert "NEBIUS_MODEL" in report["missing"]
    assert "unit-test-private-placeholder" not in str(report)


@pytest.mark.asyncio
async def test_live_preflight_cannot_claim_verification_without_access(settings, tmp_path):
    import json
    path = tmp_path / "preflight.json"
    assert await doctor(Namespace(live=True, output=path), settings) == 2
    report = json.loads(path.read_text())
    assert not report["inference_verified"] and not report["sandbox_verified"]
    assert report["checks"] == []
