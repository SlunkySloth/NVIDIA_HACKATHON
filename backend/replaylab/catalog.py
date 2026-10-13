from replaylab.config import ROOT
from replaylab.schemas import BehaviorContract, IncidentBundle, digest

TITLES = {
    "credits": ("Credits granted twice", "A customer bought 100 credits but received 200.", "100 credits, exactly once", "Credits"),
    "fulfillment": ("An order fulfilled twice", "A payment retry scheduled the same order for fulfillment twice.", "One fulfillment per paid event", "Fulfillments"),
    "subscriptions": ("Subscription rolled back", "An old update changed a cancelled subscription back to active.", "The highest entity version wins", "Subscription"),
}
RULES = {
    "credits": ["Each unique purchase event grants its stated credits once.", "Distinct purchases with equal amounts both grant credits.", "Duplicate delivery acknowledges with HTTP 200.", "Deduplication survives process restarts.", "Customer balances remain independent."],
    "fulfillment": ["Each unique paid event creates one local fulfillment.", "Distinct paid events both create fulfillment records.", "Duplicate delivery acknowledges with HTTP 200.", "Deduplication survives process restarts.", "Orders remain independent; external shipment is outside scope."],
    "subscriptions": ["Only a strictly higher entity version replaces subscription state.", "A stale event must not roll state back.", "Duplicate delivery acknowledges with HTTP 200.", "Versions persist through restarts.", "Versions are explicit fixture semantics; timestamps are not versions."],
}


def vetted_sources(fixture: str) -> dict[str, str]:
    if fixture not in TITLES:
        raise ValueError("unsupported fixture")
    directory = ROOT / "fixtures" / fixture
    paths = [directory / "handler.py", *sorted((directory / "variants").glob("*.py"))]
    return {digest(source): source for path in paths if (source := path.read_text())}


def original_source(fixture: str, revision: str | None = None) -> str:
    if revision is None:
        if fixture not in TITLES:
            raise ValueError("unsupported fixture")
        return (ROOT / "fixtures" / fixture / "handler.py").read_text()
    try:
        return vetted_sources(fixture)[revision]
    except KeyError as exc:
        raise ValueError("unsupported fixture revision; source must match a vetted handler") from exc


def contract_for(fixture: str, approved=False) -> BehaviorContract:
    return BehaviorContract(id=f"{fixture}-v1", fixture_id=fixture, approved=approved, semantics={"credits": "unique_event_credit", "fulfillment": "unique_event_fulfillment", "subscriptions": "highest_entity_version"}[fixture], rules=RULES[fixture])


def delivery(fixture, event_id="evt_001", entity="customer_01", payload=None, sequence=0):
    return {"kind": "delivery", "sequence": sequence, "event_id": event_id, "entity_id": entity, "event_type": {"credits": "purchase.succeeded", "fulfillment": "order.paid", "subscriptions": "subscription.updated"}[fixture], "payload": payload if payload is not None else {"credits": {"credits": 100}, "fulfillment": {}, "subscriptions": {"version": 2, "status": "cancelled"}}[fixture], "arrival_time": "2026-09-29T12:00:00Z"}


def sample(fixture: str) -> IncidentBundle:
    first = delivery(fixture)
    second = dict(first, sequence=1)
    if fixture == "subscriptions":
        second = delivery(fixture, "evt_old", payload={"version": 1, "status": "active"}, sequence=1)
    return IncidentBundle(schema_version="1", incident_id=f"sample-{fixture}", symptom=TITLES[fixture][1], fixture_id=fixture, revision=digest(original_source(fixture)), initial_state_hash=digest({}), steps=[first, second], contract=contract_for(fixture), provenance="original synthetic fixture")


def catalog():
    return [{"id": k, "title": v[0], "symptom": v[1], "expected": v[2], "unit": v[3], "incident": sample(k).model_dump(mode="json")} for k, v in TITLES.items()]
