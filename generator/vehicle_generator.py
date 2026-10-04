import json
import random
from datetime import date, timedelta
from pathlib import Path


# ============================================================
# ColdGuard - Vehicle Dataset Generator
# ============================================================

random.seed(84)

OUTPUT_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "vehicles.json"
)

NUMBER_OF_VEHICLES = 1500


CARRIERS = [
    "NorthLine Logistics",
    "BlueRoute Transport",
    "SwiftCold Logistics",
    "TransFresh India",
    "CoolWay Logistics",
    "PrimeFleet Transport",
    "ArcticRoute Logistics",
    "FreshMove Express",
    "National Cold Carriers",
    "SafeChain Logistics",
    "GreenRoute Transport",
    "MetroCold Logistics",
]


REFRIGERATION_MODELS = [
    "THERMO-X450",
    "THERMO-X600",
    "COLDMASTER-300",
    "COLDMASTER-500",
    "FROSTLINE-R2",
    "FROSTLINE-R4",
    "ARCTIC-500",
    "ARCTIC-700",
    "POLARTEC-350",
    "POLARTEC-550",
]


FACILITIES = [
    "FAC-0001",
    "FAC-0002",
    "FAC-0003",
    "FAC-0004",
    "FAC-0005",
    "FAC-0006",
    "FAC-0007",
    "FAC-0008",
    "FAC-0009",
    "FAC-0010",
    "FAC-0011",
    "FAC-0012",
    "FAC-0013",
    "FAC-0014",
    "FAC-0015",
]


VEHICLE_TYPES = [
    "Refrigerated Truck",
    "Refrigerated Van",
    "Refrigerated Trailer",
]


VEHICLE_STATUS = [
    "ACTIVE",
    "ACTIVE",
    "ACTIVE",
    "ACTIVE",
    "MAINTENANCE",
]


def random_maintenance_date():
    """
    Generates a maintenance date somewhere within the
    previous 12 months.
    """

    today = date.today()

    days_ago = random.randint(5, 365)

    maintenance_date = today - timedelta(
        days=days_ago
    )

    return maintenance_date.isoformat()


def generate_capacity(vehicle_type):
    if vehicle_type == "Refrigerated Van":
        return random.randint(800, 2500)

    if vehicle_type == "Refrigerated Truck":
        return random.randint(3000, 10000)

    return random.randint(9000, 22000)


def generate_vehicle(vehicle_number):
    vehicle_type = random.choice(VEHICLE_TYPES)

    current_year = date.today().year

    # Most vehicles are reasonably modern, but a smaller
    # proportion are older fleet assets.
    age_group = random.choices(
        ["NEW", "MID", "OLD"],
        weights=[30, 50, 20],
        k=1,
    )[0]

    if age_group == "NEW":
        manufacture_year = random.randint(
            current_year - 3,
            current_year,
        )

    elif age_group == "MID":
        manufacture_year = random.randint(
            current_year - 7,
            current_year - 4,
        )

    else:
        manufacture_year = random.randint(
            current_year - 14,
            current_year - 8,
        )

    vehicle_age = current_year - manufacture_year

    # Older vehicles tend to have slightly lower efficiency,
    # but the relationship is intentionally noisy.
    base_efficiency = 0.97 - (vehicle_age * 0.012)

    efficiency = base_efficiency + random.uniform(
        -0.07,
        0.07,
    )

    efficiency = max(
        0.62,
        min(0.99, efficiency),
    )

    vehicle = {
        "vehicle_id": f"TRK-{vehicle_number:05d}",
        "vehicle_type": vehicle_type,
        "carrier": random.choice(CARRIERS),
        "refrigeration_model": random.choice(
            REFRIGERATION_MODELS
        ),
        "manufacture_year": manufacture_year,
        "capacity_kg": generate_capacity(vehicle_type),
        "home_facility": random.choice(FACILITIES),
        "maintenance_date": random_maintenance_date(),
        "refrigeration_efficiency": round(
            efficiency,
            3,
        ),
        "vehicle_status": random.choice(
            VEHICLE_STATUS
        ),
    }

    return vehicle


def generate_vehicles():
    vehicles = []

    for i in range(1, NUMBER_OF_VEHICLES + 1):
        vehicles.append(
            generate_vehicle(i)
        )

    return vehicles


def main():
    print("Generating ColdGuard vehicle dataset...")

    vehicles = generate_vehicles()

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
            vehicles,
            file,
            indent=2,
        )

    print(
        f"Generated {len(vehicles):,} vehicles."
    )

    print(
        f"Saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()