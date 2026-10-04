from datetime import datetime, timezone


# ============================================================
# ColdGuard - Real-Time Alert Engine
# ============================================================


def create_alert(event, shipment, product, risk_result):
    """
    Creates a business alert when a shipment reaches
    a significant cold-chain risk level.
    """

    risk_score = risk_result["risk_score"]
    risk_level = risk_result["risk_level"]

    if risk_level not in ("HIGH", "CRITICAL"):
        return None

    # Determine the most likely immediate cause.
    reasons = risk_result["risk_reasons"]

    if "REFRIGERATION_OFF" in reasons:
        probable_cause = "REFRIGERATION_FAILURE"

    elif "DOOR_OPEN" in reasons:
        probable_cause = "DOOR_EXPOSURE"

    elif (
        "TEMPERATURE_ABOVE_RANGE" in reasons
        or "TEMPERATURE_BELOW_RANGE" in reasons
    ):
        probable_cause = "TEMPERATURE_EXCURSION"

    elif (
        "HUMIDITY_ABOVE_RANGE" in reasons
        or "HUMIDITY_BELOW_RANGE" in reasons
    ):
        probable_cause = "HUMIDITY_DEVIATION"

    else:
        probable_cause = "MULTI_FACTOR_RISK"

    alert_type = "COLD_CHAIN_RISK"

    if risk_level == "CRITICAL":
        severity = "CRITICAL"
    else:
        severity = "HIGH"

    return {
        "alert_id": (
            f"ALT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        ),

        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),

        "shipment_id": event["shipment_id"],

        "vehicle_id": event["vehicle_id"],

        "product_id": product["product_id"],

        "alert_type": alert_type,

        "severity": severity,

        "temperature": event["temperature"],

        "threshold_min": product["temperature_min"],

        "threshold_max": product["temperature_max"],

        "risk_score": risk_score,

        "risk_reasons": reasons,

        "probable_cause": probable_cause,

        "inventory_value_at_risk": shipment[
            "shipment_value"
        ],

        "status": "OPEN",
    }