import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ============================================================
# ColdGuard - Sensor Event Generator
#
# Generates realistic time-series telemetry for shipments.
#
# IMPORTANT:
# - Problem/anomaly types are NOT stored in the raw events.
# - The generator internally simulates different conditions.
# - The consumer will later infer risk from observed telemetry.
# ============================================================

random.seed(2718)

BASE_DIR = Path(__file__).resolve().parent.parent

SHIPMENT_FILE = BASE_DIR / "data" / "shipments.json"
PRODUCT_FILE = BASE_DIR / "data" / "products.json"
VEHICLE_FILE = BASE_DIR / "data" / "vehicles.json"

OUTPUT_FILE = BASE_DIR / "data" / "sensor_events.json"


# ------------------------------------------------------------
# Generation controls
# ------------------------------------------------------------

# Start with 5,000 shipments.
# Once everything works, this can be increased to 20,000,
# 50,000 or eventually the complete 100,000 shipments.
NUMBER_OF_SHIPMENTS = 5_000

# Sensor reading interval varies randomly between these values.
MIN_INTERVAL_MINUTES = 4
MAX_INTERVAL_MINUTES = 10


# ------------------------------------------------------------
# Indian route coordinates
# ------------------------------------------------------------

CITY_COORDINATES = {
    "Delhi": (28.6139, 77.2090),
    "Jaipur": (26.9124, 75.7873),
    "Lucknow": (26.8467, 80.9462),
    "Chandigarh": (30.7333, 76.7794),
    "Agra": (27.1767, 78.0081),
    "Ahmedabad": (23.0225, 72.5714),
    "Mumbai": (19.0760, 72.8777),
    "Bhopal": (23.2599, 77.4126),
    "Indore": (22.7196, 75.8577),
    "Kanpur": (26.4499, 80.3319),
    "Gurugram": (28.4595, 77.0266),
    "Noida": (28.5355, 77.3910),
    "Patna": (25.5941, 85.1376),
    "Varanasi": (25.3176, 82.9739),
    "Surat": (21.1702, 72.8311),
    "Pune": (18.5204, 73.8567),
    "Hyderabad": (17.3850, 78.4867),
    "Bengaluru": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639),
}


# ------------------------------------------------------------
# Sensor / vehicle helper values
# ------------------------------------------------------------

SENSOR_PREFIXES = [
    "SNS-",
]

ENGINE_STATES = [
    "RUNNING",
    "RUNNING",
    "RUNNING",
    "IDLE",
]

REFRIGERATION_STATES = [
    "ON",
    "ON",
    "ON",
    "ON",
]


# ------------------------------------------------------------
# Internal simulation profiles
#
# These are deliberately NOT written into sensor_events.json.
# The downstream analytics must detect their consequences.
# ------------------------------------------------------------

SIMULATION_PROFILES = [
    ("NORMAL", 70),
    ("TEMPORARY_ANOMALY", 8),
    ("DOOR_EXPOSURE", 7),
    ("ROUTE_DELAY", 5),
    ("REFRIGERATION_DEGRADATION", 4),
    ("REFRIGERATION_FAILURE", 2),
    ("RECOVERY", 2),
    ("COMBINED_STRESS", 2),
]


def choose_profile():
    names = [
        item[0]
        for item in SIMULATION_PROFILES
    ]

    weights = [
        item[1]
        for item in SIMULATION_PROFILES
    ]

    return random.choices(
        names,
        weights=weights,
        k=1,
    )[0]


def load_json(path):
    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def build_lookup(records, key):
    return {
        record[key]: record
        for record in records
    }


def parse_datetime(value):
    """
    Handles the ISO timestamps produced by shipment_generator.py.
    """

    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed


def get_coordinates(city):
    """
    Returns coordinates for a city.

    All routes in the shipment generator are represented here.
    """

    return CITY_COORDINATES.get(
        city,
        (28.6139, 77.2090),
    )


def interpolate(start, end, progress):
    """
    Linear interpolation with a small amount of geographic noise.

    For our project this is sufficient because we are simulating
    telemetry rather than calculating real road geometry.
    """

    latitude = (
        start[0]
        + (end[0] - start[0]) * progress
    )

    longitude = (
        start[1]
        + (end[1] - start[1]) * progress
    )

    # Small GPS measurement noise.
    latitude += random.uniform(
        -0.003,
        0.003,
    )

    longitude += random.uniform(
        -0.003,
        0.003,
    )

    return round(latitude, 5), round(longitude, 5)


def estimate_ambient_temperature(
    latitude,
    month,
):
    """
    Produces a plausible ambient temperature influenced by
    approximate latitude and season.

    This is synthetic, not a historical weather dataset.
    """

    seasonal_offset = 0

    if month in [4, 5, 6]:
        seasonal_offset = 7

    elif month in [11, 12, 1]:
        seasonal_offset = -4

    latitude_factor = (
        30 - latitude
    ) * 0.18

    base_temperature = (
        27
        + seasonal_offset
        + latitude_factor
    )

    return base_temperature + random.gauss(
        0,
        2.5,
    )


def estimate_ambient_humidity(
    temperature,
):
    """
    Humidity is loosely inversely related to temperature,
    with substantial natural noise.
    """

    humidity = (
        76
        - (temperature - 25) * 1.1
        + random.gauss(0, 6)
    )

    return max(
        25,
        min(98, humidity),
    )


def generate_sensor_id(vehicle_id):
    """
    Generates a stable-looking sensor identifier from a vehicle.
    """

    numeric_part = vehicle_id.replace(
        "TRK-",
        "",
    )

    return f"SNS-{numeric_part}"


def calculate_speed(
    progress,
    profile,
):
    """
    Vehicle speed varies according to journey progress and
    simulated route conditions.
    """

    # Vehicles tend to slow down near the beginning/end.
    if progress < 0.08 or progress > 0.92:
        base_speed = random.uniform(
            15,
            40,
        )

    else:
        base_speed = random.uniform(
            40,
            75,
        )

    if profile in [
        "ROUTE_DELAY",
        "COMBINED_STRESS",
    ]:
        base_speed *= random.uniform(
            0.45,
            0.75,
        )

    # Occasional traffic variation.
    base_speed += random.gauss(
        0,
        7,
    )

    return max(
        0,
        round(base_speed, 1),
    )


def calculate_door_status(
    profile,
    previous_door_status,
):
    """
    Door events are short-lived.

    Most events are CLOSED.
    """

    if previous_door_status == "OPEN":
        # Usually closes at the next reading.
        return random.choices(
            ["OPEN", "CLOSED"],
            weights=[20, 80],
            k=1,
        )[0]

    if profile in [
        "DOOR_EXPOSURE",
        "COMBINED_STRESS",
    ]:
        return random.choices(
            ["OPEN", "CLOSED"],
            weights=[18, 82],
            k=1,
        )[0]

    return random.choices(
        ["OPEN", "CLOSED"],
        weights=[3, 97],
        k=1,
    )[0]


def calculate_refrigeration_status(
    profile,
):
    if profile == "REFRIGERATION_FAILURE":
        return random.choices(
            ["OFF", "ON"],
            weights=[75, 25],
            k=1,
        )[0]

    if profile in [
        "REFRIGERATION_DEGRADATION",
        "COMBINED_STRESS",
    ]:
        return random.choices(
            ["ON", "OFF"],
            weights=[92, 8],
            k=1,
        )[0]

    return random.choices(
        REFRIGERATION_STATES,
        weights=[100, 0, 0, 0],
        k=1,
    )[0]


def calculate_temperature(
    product,
    vehicle,
    ambient_temperature,
    previous_temperature,
    door_status,
    refrigeration_status,
    profile,
    progress,
):
    """
    Temperature is the main simulated physical process.

    It depends on:
      - product's acceptable range
      - ambient conditions
      - vehicle refrigeration efficiency
      - refrigeration state
      - door state
      - previous temperature
      - journey progress
      - internal simulation condition
    """

    target_temperature = (
        product["temperature_min"]
        + product["temperature_max"]
    ) / 2

    efficiency = vehicle[
        "refrigeration_efficiency"
    ]

    # Normal thermal influence.
    ambient_influence = (
        ambient_temperature
        - target_temperature
    ) * 0.025

    # Lower efficiency means slightly more drift.
    efficiency_effect = (
        1 - efficiency
    ) * random.uniform(
        1.5,
        3.5,
    )

    # Door exposure allows ambient air into the cargo area.
    door_effect = 0

    if door_status == "OPEN":
        door_effect = random.uniform(
            0.4,
            1.4,
        )

    # Refrigeration failure/degradation.
    refrigeration_effect = 0

    if refrigeration_status == "OFF":
        refrigeration_effect = random.uniform(
            1.2,
            2.8,
        )

    elif profile == "REFRIGERATION_DEGRADATION":
        refrigeration_effect = random.uniform(
            0.15,
            0.55,
        )

    elif profile == "COMBINED_STRESS":
        refrigeration_effect = random.uniform(
            0.25,
            0.75,
        )

    # Profile-specific behavior.
    anomaly_effect = 0

    if profile == "TEMPORARY_ANOMALY":
        anomaly_effect = random.uniform(
            0.2,
            1.2,
        )

    elif profile == "DOOR_EXPOSURE":
        anomaly_effect = random.uniform(
            0.1,
            0.6,
        )

    elif profile == "REFRIGERATION_FAILURE":
        anomaly_effect = random.uniform(
            0.5,
            2.2,
        )

    elif profile == "RECOVERY":
        # Recovery behavior is handled by pulling temperature
        # gradually toward the safe target.
        anomaly_effect = -random.uniform(
            0.2,
            0.9,
        )

    # Add natural sensor noise.
    noise = random.gauss(
        0,
        0.18,
    )

    raw_target = (
        target_temperature
        + ambient_influence
        + efficiency_effect
        + door_effect
        + refrigeration_effect
        + anomaly_effect
        + noise
    )

    # Temporal smoothing makes the readings evolve rather
    # than jumping randomly between unrelated values.
    temperature = (
        previous_temperature * 0.72
        + raw_target * 0.28
    )

    # Gradually push recovery shipments back toward normal.
    if profile == "RECOVERY":
        temperature = (
            temperature * 0.70
            + target_temperature * 0.30
        )

    # A small route-position effect prevents perfectly
    # stationary behavior during long journeys.
    route_variation = math.sin(
        progress * math.pi * 3
    ) * 0.12

    temperature += route_variation

    return round(
        temperature,
        2,
    )


def calculate_humidity(
    product,
    ambient_humidity,
    temperature,
    previous_humidity,
    door_status,
):
    """
    Humidity is correlated with ambient conditions,
    temperature and door activity.
    """

    target_humidity = (
        product["humidity_min"]
        + product["humidity_max"]
    ) / 2

    ambient_component = (
        ambient_humidity * 0.18
    )

    temperature_component = (
        70 - temperature
    ) * 0.12

    door_component = (
        random.uniform(2, 8)
        if door_status == "OPEN"
        else 0
    )

    target = (
        target_humidity * 0.55
        + ambient_component
        + temperature_component
        + door_component
    )

    humidity = (
        previous_humidity * 0.72
        + target * 0.28
        + random.gauss(0, 1.8)
    )

    return round(
        max(20, min(99, humidity)),
        1,
    )


def calculate_battery(
    previous_voltage,
    refrigeration_status,
):
    """
    Simulated vehicle battery voltage.
    """

    change = random.gauss(
        0,
        0.035,
    )

    if refrigeration_status == "OFF":
        change += random.uniform(
            0.01,
            0.05,
        )

    voltage = (
        previous_voltage
        + change
    )

    return round(
        max(
            11.3,
            min(14.4, voltage),
        ),
        2,
    )


def calculate_signal_strength():
    return int(
        max(
            -110,
            min(
                -45,
                random.gauss(
                    -68,
                    9,
                ),
            ),
        )
    )


def generate_events_for_shipment(
    shipment,
    product,
    vehicle,
):
    """
    Generates a continuous sensor stream for one shipment.
    """

    departure = parse_datetime(
        shipment["departure_time"]
    )

    arrival = parse_datetime(
        shipment["actual_arrival"]
    )

    total_seconds = (
        arrival - departure
    ).total_seconds()

    # Protect against malformed/very short shipments.
    total_seconds = max(
        total_seconds,
        30 * 60,
    )

    profile = choose_profile()

    start_latlon = get_coordinates(
        shipment["origin"]
    )

    end_latlon = get_coordinates(
        shipment["destination"]
    )

    sensor_id = generate_sensor_id(
        vehicle["vehicle_id"]
    )

    target_temperature = (
        product["temperature_min"]
        + product["temperature_max"]
    ) / 2

    target_humidity = (
        product["humidity_min"]
        + product["humidity_max"]
    ) / 2

    current_time = departure

    previous_temperature = (
        target_temperature
        + random.gauss(0, 0.35)
    )

    previous_humidity = (
        target_humidity
        + random.gauss(0, 3)
    )

    previous_door_status = "CLOSED"

    previous_voltage = random.uniform(
        12.1,
        13.2,
    )

    events = []

    while current_time < arrival:
        elapsed_seconds = (
            current_time - departure
        ).total_seconds()

        progress = (
            elapsed_seconds
            / total_seconds
        )

        progress = max(
            0,
            min(1, progress),
        )

        latitude, longitude = interpolate(
            start_latlon,
            end_latlon,
            progress,
        )

        ambient_temperature = (
            estimate_ambient_temperature(
                latitude,
                current_time.month,
            )
        )

        ambient_humidity = (
            estimate_ambient_humidity(
                ambient_temperature
            )
        )

        door_status = calculate_door_status(
            profile,
            previous_door_status,
        )

        refrigeration_status = (
            calculate_refrigeration_status(
                profile
            )
        )

        temperature = calculate_temperature(
            product=product,
            vehicle=vehicle,
            ambient_temperature=ambient_temperature,
            previous_temperature=previous_temperature,
            door_status=door_status,
            refrigeration_status=refrigeration_status,
            profile=profile,
            progress=progress,
        )

        humidity = calculate_humidity(
            product=product,
            ambient_humidity=ambient_humidity,
            temperature=temperature,
            previous_humidity=previous_humidity,
            door_status=door_status,
        )

        speed = calculate_speed(
            progress,
            profile,
        )

        battery_voltage = calculate_battery(
            previous_voltage,
            refrigeration_status,
        )

        signal_strength = calculate_signal_strength()

        engine_status = random.choices(
            ENGINE_STATES,
            weights=[80, 10, 10, 5],
            k=1,
        )[0]

        event = {
            "event_id": (
                f"EVT-{random.randint(100000000, 999999999)}"
            ),
            "timestamp": (
                current_time.astimezone(
                    timezone.utc
                ).isoformat()
            ),
            "shipment_id": shipment["shipment_id"],
            "vehicle_id": vehicle["vehicle_id"],
            "sensor_id": sensor_id,
            "temperature": temperature,
            "humidity": humidity,
            "door_status": door_status,
            "refrigeration_status": refrigeration_status,
            "vehicle_speed": speed,
            "latitude": latitude,
            "longitude": longitude,
            "ambient_temperature": round(
                ambient_temperature,
                2,
            ),
            "ambient_humidity": round(
                ambient_humidity,
                1,
            ),
            "battery_voltage": battery_voltage,
            "signal_strength": signal_strength,
            "engine_status": engine_status,
        }

        events.append(event)

        previous_temperature = temperature
        previous_humidity = humidity
        previous_door_status = door_status
        previous_voltage = battery_voltage

        interval_minutes = random.uniform(
            MIN_INTERVAL_MINUTES,
            MAX_INTERVAL_MINUTES,
        )

        current_time += timedelta(
            minutes=interval_minutes
        )

    return events


def main():
    print(
        "Loading products, vehicles and shipments..."
    )

    products = load_json(PRODUCT_FILE)
    vehicles = load_json(VEHICLE_FILE)
    shipments = load_json(SHIPMENT_FILE)

    products_by_id = build_lookup(
        products,
        "product_id",
    )

    vehicles_by_id = build_lookup(
        vehicles,
        "vehicle_id",
    )

    shipments_to_process = shipments[
        :NUMBER_OF_SHIPMENTS
    ]

    print(
        f"Products loaded: {len(products):,}"
    )

    print(
        f"Vehicles loaded: {len(vehicles):,}"
    )

    print(
        f"Shipments available: {len(shipments):,}"
    )

    print(
        f"Shipments selected for telemetry: "
        f"{len(shipments_to_process):,}"
    )

    print(
        "Generating sensor events..."
    )

    all_events = []

    for index, shipment in enumerate(
        shipments_to_process,
        start=1,
    ):
        product = products_by_id.get(
            shipment["product_id"]
        )

        vehicle = vehicles_by_id.get(
            shipment["vehicle_id"]
        )

        if product is None or vehicle is None:
            continue

        events = generate_events_for_shipment(
            shipment,
            product,
            vehicle,
        )

        all_events.extend(events)

        if index % 500 == 0:
            print(
                f"Processed {index:,} shipments | "
                f"events generated: {len(all_events):,}"
            )

    print(
        f"Writing {len(all_events):,} sensor events..."
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            all_events,
            file,
            indent=2,
        )

    print()
    print(
        "Sensor generation complete."
    )
    print(
        f"Total sensor events: {len(all_events):,}"
    )
    print(
        f"Saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()