import json
import random
from pathlib import Path


# ============================================================
# ColdGuard - Product Dataset Generator
# Generates realistic product/reference data for cold-chain
# analytics.
# ============================================================

random.seed(42)

OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "products.json"

NUMBER_OF_PRODUCTS = 1000


PRODUCT_PROFILES = [
    {
        "category": "Dairy",
        "sub_categories": [
            "Fresh Milk",
            "Paneer",
            "Yogurt",
            "Cheese",
            "Butter",
            "Cream",
        ],
        "temperature_range": (1.0, 5.0),
        "humidity_range": (55, 85),
        "shelf_life": (5, 30),
        "unit_cost": (35, 450),
        "unit_price_multiplier": (1.20, 1.55),
    },
    {
        "category": "Fresh Produce",
        "sub_categories": [
            "Leafy Vegetables",
            "Fruits",
            "Berries",
            "Cut Vegetables",
            "Herbs",
        ],
        "temperature_range": (2.0, 10.0),
        "humidity_range": (70, 95),
        "shelf_life": (3, 20),
        "unit_cost": (30, 350),
        "unit_price_multiplier": (1.15, 1.60),
    },
    {
        "category": "Meat & Poultry",
        "sub_categories": [
            "Chicken",
            "Mutton",
            "Processed Meat",
            "Poultry Products",
        ],
        "temperature_range": (0.0, 4.0),
        "humidity_range": (70, 90),
        "shelf_life": (2, 12),
        "unit_cost": (180, 850),
        "unit_price_multiplier": (1.15, 1.45),
    },
    {
        "category": "Seafood",
        "sub_categories": [
            "Fresh Fish",
            "Prawns",
            "Shellfish",
            "Processed Seafood",
        ],
        "temperature_range": (-1.0, 3.0),
        "humidity_range": (75, 95),
        "shelf_life": (2, 10),
        "unit_cost": (250, 1200),
        "unit_price_multiplier": (1.15, 1.50),
    },
    {
        "category": "Frozen Foods",
        "sub_categories": [
            "Frozen Vegetables",
            "Frozen Meat",
            "Frozen Seafood",
            "Frozen Snacks",
            "Ice Cream",
        ],
        "temperature_range": (-25.0, -12.0),
        "humidity_range": (60, 90),
        "shelf_life": (60, 365),
        "unit_cost": (80, 700),
        "unit_price_multiplier": (1.15, 1.50),
    },
    {
        "category": "Pharmaceuticals",
        "sub_categories": [
            "Vaccines",
            "Biologics",
            "Insulin",
            "Injectables",
            "Temperature-Sensitive Medicines",
        ],
        "temperature_range": (2.0, 8.0),
        "humidity_range": (30, 70),
        "shelf_life": (90, 730),
        "unit_cost": (500, 15000),
        "unit_price_multiplier": (1.10, 1.35),
    },
    {
        "category": "Bakery",
        "sub_categories": [
            "Fresh Bread",
            "Cakes",
            "Pastries",
            "Cream Products",
        ],
        "temperature_range": (2.0, 8.0),
        "humidity_range": (50, 80),
        "shelf_life": (2, 15),
        "unit_cost": (40, 500),
        "unit_price_multiplier": (1.25, 1.70),
    },
    {
        "category": "Ready-to-Eat Foods",
        "sub_categories": [
            "Prepared Meals",
            "Salads",
            "Sandwiches",
            "Meal Kits",
        ],
        "temperature_range": (2.0, 6.0),
        "humidity_range": (55, 85),
        "shelf_life": (2, 12),
        "unit_cost": (70, 450),
        "unit_price_multiplier": (1.20, 1.60),
    },
]


SUPPLIER_COUNT = 250


BRANDS = [
    "FreshHarvest",
    "PureLife",
    "DailyFresh",
    "FarmNest",
    "NatureBasket",
    "GreenValley",
    "HealthFirst",
    "PrimeFoods",
    "ColdPure",
    "UrbanHarvest",
    "WellSpring",
    "FreshRoute",
    "NutriCare",
    "FarmDirect",
    "GoodFoods",
]


def random_product_name(sub_category):
    """
    Creates a reasonably natural product name without making
    every record identical.
    """

    brand = random.choice(BRANDS)

    variants = [
        "Premium",
        "Classic",
        "Fresh",
        "Select",
        "Natural",
        "Daily",
        "Farm Fresh",
        "Prime",
        "Organic",
        "Standard",
    ]

    variant = random.choice(variants)

    return f"{brand} {variant} {sub_category}"


def generate_product(product_number):
    profile = random.choice(PRODUCT_PROFILES)

    category = profile["category"]
    sub_category = random.choice(profile["sub_categories"])

    temp_min, temp_max = profile["temperature_range"]
    humidity_min, humidity_max = profile["humidity_range"]

    shelf_min, shelf_max = profile["shelf_life"]
    cost_min, cost_max = profile["unit_cost"]

    # Add small variation to the reference limits so products
    # within the same category are not identical.
    temperature_min = round(
        temp_min + random.uniform(-0.3, 0.3),
        1,
    )

    temperature_max = round(
        temp_max + random.uniform(-0.3, 0.3),
        1,
    )

    humidity_min_value = max(
        20,
        min(
            90,
            round(humidity_min + random.uniform(-3, 3))
        ),
    )

    humidity_max_value = min(
        100,
        max(
            humidity_min_value + 5,
            round(humidity_max + random.uniform(-3, 3))
        ),
    )

    shelf_life_days = random.randint(
        shelf_min,
        shelf_max,
    )

    unit_cost = round(
        random.uniform(cost_min, cost_max),
        2,
    )

    price_multiplier = random.uniform(
        *profile["unit_price_multiplier"]
    )

    unit_price = round(
        unit_cost * price_multiplier,
        2,
    )

    supplier_id = f"SUP-{random.randint(1, SUPPLIER_COUNT):04d}"

    product = {
        "product_id": f"PRD-{product_number:06d}",
        "product_name": random_product_name(sub_category),
        "category": category,
        "sub_category": sub_category,
        "temperature_min": temperature_min,
        "temperature_max": temperature_max,
        "humidity_min": humidity_min_value,
        "humidity_max": humidity_max_value,
        "shelf_life_days": shelf_life_days,
        "unit_cost": unit_cost,
        "unit_price": unit_price,
        "supplier_id": supplier_id,
    }

    return product


def generate_products():
    products = []

    for i in range(1, NUMBER_OF_PRODUCTS + 1):
        products.append(generate_product(i))

    return products


def main():
    print("Generating ColdGuard product dataset...")

    products = generate_products()

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
            products,
            file,
            indent=2,
        )

    print(f"Generated {len(products):,} products.")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()