"""Published input contracts. All imports are data, never executable archives."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FixtureId = Literal["credits", "fulfillment", "subscriptions"]


def digest(value: Any) -> str:
    raw = value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Delivery(StrictModel):
    kind: Literal["delivery"] = "delivery"
    sequence: int = Field(ge=0)
    event_id: str = Field(min_length=1, max_length=100, pattern=r"^[\w.-]+$")
    entity_id: str = Field(min_length=1, max_length=100, pattern=r"^[\w.-]+$")
    event_type: str = Field(max_length=80)
    payload: dict[str, Any]
    arrival_time: datetime

    @model_validator(mode="after")
    def bounded_payload(self):
        if len(json.dumps(self.payload)) > 4096:
            raise ValueError("payload exceeds 4 KiB")
        return self


class Restart(StrictModel):
    kind: Literal["restart"] = "restart"
    sequence: int = Field(ge=0)


class BehaviorContract(StrictModel):
    id: str = Field(max_length=100)
    version: Literal["1"] = "1"
    fixture_id: FixtureId
    approved: bool = False
    deduplication_key: Literal["event_id"] = "event_id"
    semantics: Literal["unique_event_credit", "unique_event_fulfillment", "highest_entity_version"]
    acknowledgement_status: Literal[200] = 200
    rules: list[str] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def correct_semantics(self):
        expected = {"credits": "unique_event_credit", "fulfillment": "unique_event_fulfillment", "subscriptions": "highest_entity_version"}
        if self.semantics != expected[self.fixture_id]:
            raise ValueError("contract semantics do not match supported fixture")
        if any(len(rule) > 500 for rule in self.rules):
            raise ValueError("contract rule too long")
        return self


class IncidentBundle(StrictModel):
    schema_version: Literal["1"] = "1"
    incident_id: str = Field(min_length=1, max_length=100)
    symptom: str = Field(min_length=1, max_length=500)
    fixture_id: FixtureId
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    runtime_build: Literal["deploy/sandbox.Dockerfile"] = "deploy/sandbox.Dockerfile"
    initial_state: dict[str, Any] = Field(default_factory=dict)
    initial_state_hash: str
    steps: list[Delivery | Restart] = Field(min_length=1, max_length=32)
    contract: BehaviorContract
    provenance: Literal["original synthetic fixture", "sanitized local import"]
    redacted: Literal[True] = True

    @model_validator(mode="after")
    def validate_adapter(self):
        if self.initial_state_hash != digest(self.initial_state):
            raise ValueError("initial state hash mismatch")
        if self.contract.fixture_id != self.fixture_id:
            raise ValueError("contract belongs to another fixture")
        if [s.sequence for s in self.steps] != list(range(len(self.steps))):
            raise ValueError("sequence indexes must be contiguous and ordered starting at zero")
        if not any(isinstance(s, Delivery) for s in self.steps):
            raise ValueError("incident requires at least one delivery")
        for entity, value in self.initial_state.items():
            if not entity or len(entity) > 100:
                raise ValueError("invalid initial-state entity")
            if self.fixture_id == "subscriptions":
                if not isinstance(value, dict) or set(value) != {"status", "version"} or not isinstance(value["status"], str) or value["status"] not in {"active", "cancelled", "past_due"} or type(value["version"]) is not int or value["version"] < 0:
                    raise ValueError("subscription state requires a supported status and nonnegative version")
            elif type(value) is not int or value < 0 or value > 1000000:
                raise ValueError("initial counts must be nonnegative integers below one million")
        for step in self.steps:
            if isinstance(step, Restart):
                continue
            expected_type = {"credits": "purchase.succeeded", "fulfillment": "order.paid", "subscriptions": "subscription.updated"}[self.fixture_id]
            if step.event_type != expected_type:
                raise ValueError(f"unsupported event type: expected {expected_type}")
            p = step.payload
            if self.fixture_id == "credits" and (set(p) != {"credits"} or type(p["credits"]) is not int or not 1 <= p["credits"] <= 1000000):
                raise ValueError("credit payload requires an integer credits amount between 1 and 1000000")
            if self.fixture_id == "fulfillment" and p != {}:
                raise ValueError("fulfillment payload must be empty")
            if self.fixture_id == "subscriptions" and (set(p) != {"version", "status"} or type(p["version"]) is not int or p["version"] < 1 or not isinstance(p["status"], str) or p["status"] not in {"active", "cancelled", "past_due"}):
                raise ValueError("subscription payload requires a positive integer version and supported status")
        seen = {}
        for step in self.steps:
            if isinstance(step, Delivery):
                signature = (step.entity_id, step.event_type, digest(step.payload))
                if step.event_id in seen and seen[step.event_id] != signature:
                    raise ValueError("same event ID cannot identify conflicting payloads")
                seen[step.event_id] = signature
        return self


class CreateRun(StrictModel):
    incident_id: str
    mode: Literal["reference", "live", "flawed"] = "reference"
    idempotency_key: str = Field(min_length=8, max_length=100)
