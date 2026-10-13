import json

import httpx
import pytest
from replaylab.models.nebius import Nemotron
from replaylab.models.policy import Candidate


def test_live_adapter_rejects_an_unrelated_model_before_network_access(settings):
    settings.model = "unrelated/model"
    with pytest.raises(ValueError, match="NVIDIA"):
        Nemotron(settings)


async def mock_model(settings, handler):
    settings.api_key, settings.model = "unit-test-placeholder", "nvidia/test-model"
    model = Nemotron(settings)
    await model.client.aclose()
    model.client = httpx.AsyncClient(base_url=settings.inference_url + "/", transport=httpx.MockTransport(handler))
    return model


@pytest.mark.asyncio
async def test_structured_model_output_records_real_usage_and_exact_model(settings):
    def response(request):
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        content = {"explanation": "Persistent event identity prevents duplicate grants.", "path": "handler.py", "source": "def handle(db, event):\n    return {'accepted': True}\n"}
        return httpx.Response(200, json={"model": "nvidia/resolved-test-model", "usage": {"total_tokens": 321, "prompt_tokens": 201, "completion_tokens": 120}, "choices": [{"message": {"content": json.dumps(content)}}]})
    model = await mock_model(settings, response)
    try:
        assert (await model.request(Candidate, {"source": "evidence"})).path == "handler.py"
        assert model.used_tokens == 321
        assert model.calls[0]["model"] == "nvidia/resolved-test-model"
        assert model.calls[0]["status"] == "validated"
    finally:
        await model.close()


@pytest.mark.asyncio
async def test_failed_provider_requests_still_consume_the_reserved_budget(settings):
    model = await mock_model(settings, lambda request: httpx.Response(503, text="private provider diagnostics"))
    try:
        with pytest.raises(RuntimeError, match="HTTP 503"):
            await model.request(Candidate, {"source": "evidence"})
        assert model.used_tokens > 4000
        assert model.calls[0]["budgeted_tokens"] == model.used_tokens
        assert "private provider diagnostics" not in json.dumps(model.calls)
    finally:
        await model.close()


@pytest.mark.asyncio
async def test_no_network_request_is_made_when_the_prompt_budget_is_exhausted(settings):
    requests = []
    model = await mock_model(settings, lambda request: requests.append(request))
    settings.token_budget = 1
    try:
        with pytest.raises(RuntimeError, match="budget exhausted"):
            await model.request(Candidate, {"source": "evidence"})
        assert requests == [] and model.calls == []
    finally:
        await model.close()
