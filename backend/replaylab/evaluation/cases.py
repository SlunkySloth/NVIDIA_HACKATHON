"""Original development/holdout cases, defined before live model evaluation."""
from replaylab.catalog import contract_for, delivery, sample
from replaylab.config import ROOT
from replaylab.replay.scenarios import indexed
from replaylab.schemas import IncidentBundle, digest

DATASET_VERSION = "1"


def case(name, fixture, variant, symptom, steps, initial=None, defective=True):
    initial = initial or {}
    source = (ROOT / "fixtures" / fixture / "variants" / f"{variant}.py").read_text()
    incident = IncidentBundle(incident_id=name, fixture_id=fixture, symptom=symptom, revision=digest(source), initial_state=initial, initial_state_hash=digest(initial), steps=indexed(steps), contract=contract_for(fixture, approved=True), provenance="original synthetic fixture")
    return {"name": name, "defective": defective, "incident": incident.model_dump(mode="json")}


def cases(split="holdout"):
    if split == "development":
        basic = []
        for fixture in ("credits", "fulfillment", "subscriptions"):
            incident = sample(fixture).model_dump(mode="json")
            incident["contract"]["approved"] = True
            basic.append({"name": f"development-{fixture}", "defective": True, "incident": incident})
        first = delivery("credits", "dev_purchase_a", "dev_customer", {"credits": 20})
        second = delivery("credits", "dev_purchase_b", "dev_customer", {"credits": 75})
        return basic + [case("development-later-purchase", "credits", "entity", "A customer's later purchase did not add its credits.", [first, second])]
    if split != "holdout":
        raise ValueError("evaluation split must be development or holdout")
    purchase = delivery("credits", "purchase_retry_91", "customer_91", {"credits": 37})
    equal_a = delivery("credits", "purchase_equal_a", "customer_42", {"credits": 45})
    equal_b = delivery("credits", "purchase_equal_b", "customer_42", {"credits": 45})
    order_a = delivery("fulfillment", "payment_a", "order_a")
    order_b = delivery("fulfillment", "payment_b", "order_b")
    state_a = delivery("subscriptions", "update_a", "account_c", {"version": 4, "status": "cancelled"})
    state_b = delivery("subscriptions", "update_b", "account_c", {"version": 4, "status": "active"})
    return [
        case("holdout-retry-after-restart", "credits", "memory", "A retry after a restart granted the same purchase again.", [purchase, {"kind": "restart"}, purchase], {"customer_91": 17}),
        case("holdout-equal-purchases", "credits", "amount", "Two paid purchases of equal size added credits only once.", [equal_a, equal_b, equal_a], {"customer_42": 13}),
        case("holdout-two-orders", "fulfillment", "global", "A second paid order was acknowledged without fulfillment.", [order_a, order_b, order_a]),
        case("holdout-independent-ledgers", "fulfillment", "shared", "A paid order increased another order's fulfillment count.", [order_b, order_a], {"order_a": 3}),
        case("holdout-entity-versions", "subscriptions", "global_version", "A new customer's subscription update was ignored.", [state_a], {"account_other": {"status": "active", "version": 11}}),
        case("holdout-equal-versions", "subscriptions", "equal_version", "An equal-version update replaced the first accepted state.", [state_a, state_b]),
        case("clean-credit-retries", "credits", "clean", "Inspect a credit purchase retry that preserved the expected balance.", [purchase, {"kind": "restart"}, purchase], {"customer_91": 17}, defective=False),
        case("clean-subscription-order", "subscriptions", "clean", "Inspect a subscription update sequence that retained the latest state.", [state_a, state_b, {"kind": "restart"}, state_b], defective=False),
    ]
