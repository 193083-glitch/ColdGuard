import json
import sys
import os
from pathlib import Path

from pymongo import MongoClient
from kafka import KafkaConsumer
from dotenv import load_dotenv


# ============================================================
# Add ColdGuard project root to Python module path
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

sys.path.append(str(BASE_DIR))


# ============================================================
# Load environment variables
# ============================================================

load_dotenv(BASE_DIR / ".env")


# ============================================================
# ColdGuard processing modules
# ============================================================

from processing.risk_engine import (
    load_products,
    calculate_risk,
)

from processing.alert_engine import create_alert


# ============================================================
# Configuration
# ============================================================

PRODUCT_FILE = BASE_DIR / "data" / "products.json"
SHIPMENT_FILE = BASE_DIR / "data" / "shipments.json"

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC_NAME = "coldchain.sensor.events"

MONGO_URI = os.getenv("MONGO_URI")

DATABASE_NAME = "ColdGuard"


# ============================================================
# Load shipment reference data
# ============================================================

def load_shipments():

    print("Loading shipment information...")

    with open(
        SHIPMENT_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        shipments = json.load(file)

    return {
        shipment["shipment_id"]: shipment
        for shipment in shipments
    }


# ============================================================
# Create Kafka consumer
# ============================================================

def create_consumer():

    return KafkaConsumer(
        TOPIC_NAME,

        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,

        auto_offset_reset="earliest",

        group_id="coldguard-risk-engine-atlas",

        enable_auto_commit=True,

        value_deserializer=lambda value: json.loads(
            value.decode("utf-8")
        ),
    )


# ============================================================
# Main streaming application
# ============================================================

def main():

    print("=" * 60)
    print("COLDGUARD - REAL-TIME RISK ENGINE")
    print("=" * 60)

    # --------------------------------------------------------
    # Check Atlas connection string
    # --------------------------------------------------------

    if not MONGO_URI:

        print()
        print("ERROR: MONGO_URI was not found.")
        print("Make sure your .env file contains:")
        print("MONGO_URI=your_atlas_connection_string")
        return

    # --------------------------------------------------------
    # Load reference data
    # --------------------------------------------------------

    print()
    print("Loading product rules...")

    products = load_products(PRODUCT_FILE)

    print(
        f"Loaded {len(products):,} products."
    )

    shipments = load_shipments()

    print(
        f"Loaded {len(shipments):,} shipments."
    )

    # --------------------------------------------------------
    # Connect to MongoDB Atlas
    # --------------------------------------------------------

    print()
    print("Connecting to MongoDB Atlas...")

    mongo_client = MongoClient(
        MONGO_URI
    )

    db = mongo_client[
        DATABASE_NAME
    ]

    sensor_collection = db[
        "sensor_events"
    ]

    alert_collection = db[
        "alerts"
    ]

    # Test MongoDB Atlas connection
    mongo_client.admin.command(
        "ping"
    )

    print(
        "Connected to MongoDB Atlas successfully."
    )

    # --------------------------------------------------------
    # Connect to Kafka
    # --------------------------------------------------------

    print()
    print(
        f"Connecting to Kafka: "
        f"{KAFKA_BOOTSTRAP_SERVERS}"
    )

    consumer = create_consumer()

    print(
        f"Listening to topic: "
        f"{TOPIC_NAME}"
    )

    print()
    print("Risk engine is LIVE.")
    print("Data will be written to MongoDB Atlas.")
    print("Press Ctrl+C to stop.")
    print()

    # --------------------------------------------------------
    # Runtime counters
    # --------------------------------------------------------

    processed = 0
    enriched = 0
    high_risk = 0
    alerts_created = 0

    # --------------------------------------------------------
    # Streaming loop
    # --------------------------------------------------------

    try:

        for message in consumer:

            event = message.value

            # ------------------------------------------------
            # Store raw sensor event in Atlas
            # ------------------------------------------------

            sensor_collection.insert_one(
                event
            )

            shipment_id = event[
                "shipment_id"
            ]

            # ------------------------------------------------
            # Shipment enrichment
            # ------------------------------------------------

            shipment = shipments.get(
                shipment_id
            )

            if shipment is None:

                continue

            product_id = shipment[
                "product_id"
            ]

            product = products.get(
                product_id
            )

            if product is None:

                continue

            # ------------------------------------------------
            # Calculate real-time risk
            # ------------------------------------------------

            result = calculate_risk(
                event,
                product,
            )

            processed += 1
            enriched += 1

            # ------------------------------------------------
            # Track high-risk events
            # ------------------------------------------------

            if result["risk_level"] in (
                "HIGH",
                "CRITICAL",
            ):

                high_risk += 1

            # ------------------------------------------------
            # Create business alert
            # ------------------------------------------------

            alert = create_alert(
                event,
                shipment,
                product,
                result,
            )

            if alert is not None:

                alert_collection.insert_one(
                    alert
                )

                alerts_created += 1

                print()
                print("🚨 ALERT GENERATED")

                print(
                    f"    Shipment: "
                    f"{alert['shipment_id']}"
                )

                print(
                    f"    Severity: "
                    f"{alert['severity']}"
                )

                print(
                    f"    Risk: "
                    f"{alert['risk_score']}"
                )

                print(
                    f"    Cause: "
                    f"{alert['probable_cause']}"
                )

                print(
                    f"    Value at Risk: "
                    f"₹"
                    f"{alert['inventory_value_at_risk']:,.2f}"
                )

                print()

            # ------------------------------------------------
            # Display selected streaming events
            # ------------------------------------------------

            if (
                processed <= 10
                or processed % 1000 == 0
                or result["risk_level"]
                in (
                    "HIGH",
                    "CRITICAL",
                )
            ):

                print(
                    f"[{processed:,}] "
                    f"{shipment_id} | "
                    f"{product['category']} | "
                    f"Temp: "
                    f"{event['temperature']:.2f}°C | "
                    f"Risk: "
                    f"{result['risk_score']} | "
                    f"{result['risk_level']}"
                )

                if result[
                    "risk_reasons"
                ]:

                    print(
                        "    Reasons: "
                        + ", ".join(
                            result[
                                "risk_reasons"
                            ]
                        )
                    )

    # --------------------------------------------------------
    # Stop streaming
    # --------------------------------------------------------

    except KeyboardInterrupt:

        print()
        print(
            "Risk engine stopped by user."
        )

    # --------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------

    finally:

        consumer.close()

        mongo_client.close()

        print()
        print(
            f"Events processed: "
            f"{processed:,}"
        )

        print(
            f"Events enriched: "
            f"{enriched:,}"
        )

        print(
            f"High/Critical events: "
            f"{high_risk:,}"
        )

        print(
            f"Alerts generated: "
            f"{alerts_created:,}"
        )

        print(
            "Consumer shut down."
        )


# ============================================================
# Program entry point
# ============================================================

if __name__ == "__main__":

    main()