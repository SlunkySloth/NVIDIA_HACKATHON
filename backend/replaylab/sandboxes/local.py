import asyncio
import importlib.util
import threading

from replaylab.catalog import vetted_sources
from replaylab.config import ROOT
from replaylab.replay.runner import regression, replay

FLAWS = ("memory", "ignore_later", "amount", "entity_shared", "no_effect")


def baseline(fixture, flawed=False, flaw="memory"):
    spec = importlib.util.spec_from_file_location("reference", ROOT / "evals/baselines/reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.flawed_source(fixture, flaw) if flawed else module.source(fixture)


class LocalReference:
    provider = "local trusted reference (development only)"

    def __init__(self, fixture):
        self.fixture = fixture
        self.allowed_sources = set(vetted_sources(fixture).values()) | {baseline(fixture)} | {baseline(fixture, True, flaw) for flaw in FLAWS}
        self.operation_ids = []
        self.cancel_event = threading.Event()

    async def _run(self, operation, source, fixture, initial, data):
        if fixture != self.fixture or source not in self.allowed_sources:
            raise ValueError("local adapter refuses generated or imported source; use Token Factory Sandboxes")
        task = asyncio.create_task(asyncio.to_thread(operation, source, fixture, initial, data, cancel_event=self.cancel_event))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            self.cancel_event.set()
            await asyncio.shield(task)
            raise

    async def replay(self, source, fixture, initial, scenario):
        return await self._run(replay, source, fixture, initial, scenario)

    async def regression(self, source, fixture, initial, test):
        from replaylab.models.policy import validate_test
        validate_test(test)
        return await self._run(regression, source, fixture, initial, test)

    async def close(self):
        self.cancel_event.set()
