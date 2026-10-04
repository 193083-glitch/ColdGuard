import json
import random
from datetime import datetime, timedelta
from pathlib import Path


# ============================================================
# ColdGuard - Shipment Dataset Generator
# ============================================================

random.seed(126)

BASE_DIR = Path(__file__).resolve().parent.parent

PRODUCT_FILE = BASE_DIR / "data" / "products.json"
VEHICLE_FILE = BASE_DIR / "data" / "vehicles.json"
OUTPUT_FILE = BASE_DIR / "data" / "shipments.json"

NUMBER_OF_SHIPMENTS = 100_000


ROUTES = [
    ("Delhi", "Jaipur", 280),
    ("Delhi", "Lucknow", 550),
    ("Delhi", "Chandigarh", 245),
    ("Delhi", "Agra", 235),
    ("Delhi", "Ahmedabad", 940),
    ("Delhi", "Mumbai", 1420),
    ("Delhi", "Bhopal", 780),
    ("Delhi", "Indore", 810),
    ("Delhi", "Kanpur", 480),
    ("Delhi", "Gurugram", 35),
    ("Delhi", "Noida", 25),
    ("Jaipur", "Delhi", 280),
    ("Jaipur", "Ahmedabad", 670),
    ("Jaipur", "Lucknow", 700),
    ("Lucknow", "Delhi", 550),
    ("Lucknow", "Kanpur", 90),
    ("Lucknow", "Patna", 530),
    ("Lucknow", "Varanasi", 320),
    ("Ahmedabad", "Mumbai", 530),
    ("Ahmedabad", "Indore", 400),
    ("Mumbai", "Pune", 150),
    ("Mumbai", "Surat", 285),
    ("Mumbai", "Ahmedabad", 530),
    ("Pune", "Mumbai", 150),
    ("Pune", "Hyderabad", 560),
    ("Hyderabad", "Bengaluru", 570),
    ("Bengaluru", "Chennai", 350),
    ("Chennai", "Bengaluru", 350),
    ("Kolkata", "Patna", 580),
    ("Patna", "Lucknow", 530),
    ("Bhopal", "Indore", 190),
    ("Indore", "Ahmedabad", 400),
]


PRIORITIES = [
    "LOW",
    "MEDIUM",
    "MEDIUM",
    "MEDIUM",
    "HIGH",
]


def load_json(file_path):
    with open(
        file_path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def random_departure_time():
    """
    Generates shipment departure times over roughly
    the previous six months.
    """

    now = datetime.now()

    days_ago = random.randint(0, 180)

    random_time = now - timedelta(
        days=days_ago,
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )

    return random_time


def calculate_travel_hours(distance_km):
    """
    Approximate transport duration.

    We deliberately add noise because actual journey time
    depends on traffic, stops, weather and route conditions.
    """

    average_speed = random.uniform(
        38,
        58,
    )

    base_hours = distance_km / average_speed

    delay_hours = random.choices(
        [
            0,
            random.uniform(0.5, 2),
            random.uniform(2, 6),
            random.uniform(6, 12),
        ],
        weights=[
            65,
            20,
            11,
            4,
        ],
        k=1,
    )[0]

    return base_hours + delay_hours


def generate_shipment(
    shipment_number,
    products,
    vehicles,
):
    product = random.choice(products)
    vehicle = random.choice(vehicles)

    origin, destination, distance_km = random.choice(
        ROUTES
    )

    departure_time = random_departure_time()

    travel_hours = calculate_travel_hours(
        distance_km
    )

    expected_hours = (
        distance_km / random.uniform(45, 55)
    )

    expected_arrival = (
        departure_time
        + timedelta(hours=expected_hours)
    )

    actual_arrival = (
        departure_time
        + timedelta(hours=travel_hours)
    )

    # Quantity is constrained by vehicle capacity,
    # but does not always fill the vehicle.
    maximum_quantity = max(
        50,
        int(vehicle["capacity_kg"] * random.uniform(0.35, 0.92))
    )

    quantity = random.randint(
        50,
        maximum_quantity,
    )

    unit_value = product["unit_cost"]

    shipment_value = round(
        quantity * unit_value,
        2,
    )

    # Most shipments arrive normally, but some are delayed.
    delay_hours = (
        actual_arrival - expected_arrival
    ).total_seconds() / 3600

    if delay_hours > 6:
        status = "DELIVERED_LATE"
    elif delay_hours > 0.5:
        status = random.choice(
            [
                "DELIVERED",
                "DELIVERED",
                "DELIVERED_LATE",
            ]
        )
    else:
        status = "DELIVERED"

    shipment = {
        "shipment_id": (
            f"SHP-{departure_time.year}-"
            f"{shipment_number:07d}"
        ),
        "product_id": product["product_id"],
        "vehicle_id": vehicle["vehicle_id"],
        "origin": origin,
        "destination": destination,
        "quantity": quantity,
        "unit_value": unit_value,
        "shipment_value": shipment_value,
        "departure_time": departure_time.isoformat(),
        "expected_arrival": expected_arrival.isoformat(),
        "actual_arrival": actual_arrival.isoformat(),
        "distance_km": distance_km,
        "priority": random.choice(PRIORITIES),
        "status": status,
    }

    return shipment


def generate_shipments(
    products,
    vehicles,
):
    shipments = []

    for i in range(
        1,
        NUMBER_OF_SHIPMENTS + 1,
    ):
        shipments.append(
            generate_shipment(
                i,
                products,
                vehicles,
            )
        )

        if i % 10_000 == 0:
            print(
                f"Generated {i:,} shipments..."
            )

    return shipments


def main():
    print(
        "Loading products and vehicles..."
    )

    products = load_json(PRODUCT_FILE)
    vehicles = load_json(VEHICLE_FILE)

    print(
        f"Loaded {len(products):,} products."
    )

    print(
        f"Loaded {len(vehicles):,} vehicles."
    )

    print(
        "Generating shipments..."
    )

    shipments = generate_shipments(
        products,
        vehicles,
    )

    print(
        "Writing shipment dataset..."
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            shipments,
            file,
            indent=2,
        )

    print(
        f"Generated {len(shipments):,} shipments."
    )

    print(
        f"Saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()