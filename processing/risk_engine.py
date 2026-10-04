import json


def load_products(product_file):
    """
    Load product temperature and humidity thresholds.
    """

    with open(product_file, "r", encoding="utf-8") as file:
        products = json.load(file)

    return {
        product["product_id"]: product
        for product in products
    }


def calculate_risk(event, product):
    """
    Calculate a 0-100 cold-chain risk score
    using the specific product's requirements.
    """

    temperature = event["temperature"]
    humidity = event["humidity"]

    temp_min = product["temperature_min"]
    temp_max = product["temperature_max"]

    humidity_min = product["humidity_min"]
    humidity_max = product["humidity_max"]

    score = 0
    reasons = []

    # --------------------------------------------------------
    # Temperature deviation
    # --------------------------------------------------------

    if temperature < temp_min:

        deviation = temp_min - temperature

        score += min(40, deviation * 10)

        reasons.append("TEMPERATURE_BELOW_RANGE")

    elif temperature > temp_max:

        deviation = temperature - temp_max

        score += min(40, deviation * 10)

        reasons.append("TEMPERATURE_ABOVE_RANGE")

    # --------------------------------------------------------
    # Humidity deviation
    # --------------------------------------------------------

    if humidity < humidity_min:

        deviation = humidity_min - humidity

        score += min(15, deviation * 0.5)

        reasons.append("HUMIDITY_BELOW_RANGE")

    elif humidity > humidity_max:

        deviation = humidity - humidity_max

        score += min(15, deviation * 0.5)

        reasons.append("HUMIDITY_ABOVE_RANGE")

    # --------------------------------------------------------
    # Door exposure
    # --------------------------------------------------------

    if event["door_status"] == "OPEN":

        score += 15

        reasons.append("DOOR_OPEN")

    # --------------------------------------------------------
    # Refrigeration condition
    # --------------------------------------------------------

    if event["refrigeration_status"] != "ON":

        score += 25

        reasons.append("REFRIGERATION_OFF")

    # --------------------------------------------------------
    # Engine condition
    # --------------------------------------------------------

    if event["engine_status"] != "RUNNING":

        score += 5

        reasons.append("ENGINE_NOT_RUNNING")

    # --------------------------------------------------------
    # Final score
    # --------------------------------------------------------

    score = min(round(score), 100)

    if score >= 76:
        risk_level = "CRITICAL"

    elif score >= 51:
        risk_level = "HIGH"

    elif score >= 26:
        risk_level = "WATCH"

    else:
        risk_level = "NORMAL"

    return {
        "risk_score": score,
        "risk_level": risk_level,
        "risk_reasons": reasons
    }