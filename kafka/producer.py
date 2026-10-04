import json
import time
from pathlib import Path

from kafka import KafkaProducer
from kafka.errors import KafkaError


# ============================================================
# ColdGuard - Kafka Sensor Producer
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

SENSOR_FILE = (
    BASE_DIR
    / "data"
    / "sensor_events.json"
)

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"

TOPIC_NAME = "coldchain.sensor.events"

# Controls how quickly historical sensor records are replayed.
# 0.05 means approximately 20 events/second.
STREAM_DELAY_SECONDS = 0.05


def create_producer():
    """
    Creates the Kafka producer.
    """

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,

        # Convert Python dictionaries to JSON bytes.
        value_serializer=lambda value: json.dumps(
            value
        ).encode("utf-8"),

        # Make the producer more reliable.
        acks="all",

        retries=5,

        linger_ms=10,

        batch_size=32_768,
    )

    return producer


def load_sensor_events():
    """
    Loads the generated sensor dataset.
    """

    print(
        f"Loading sensor events from: {SENSOR_FILE}"
    )

    with open(
        SENSOR_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def stream_events(producer, events):
    """
    Sends sensor events continuously to Kafka.
    """

    total_events = len(events)

    print()
    print(
        f"Starting stream of {total_events:,} events..."
    )

    print(
        f"Kafka topic: {TOPIC_NAME}"
    )

    print(
        f"Replay delay: {STREAM_DELAY_SECONDS} seconds"
    )

    print()
    print(
        "Press Ctrl+C to stop the producer."
    )

    try:

        for index, event in enumerate(
            events,
            start=1,
        ):

            # Use shipment_id as the Kafka key.
            #
            # This helps keep events belonging to the same
            # shipment ordered within a Kafka partition.
            shipment_id = event[
                "shipment_id"
            ]

            producer.send(
                TOPIC_NAME,
                key=shipment_id.encode(
                    "utf-8"
                ),
                value=event,
            )

            # Occasionally wait for Kafka acknowledgement.
            if index % 100 == 0:
                producer.flush()

            if (
                index == 1
                or index % 1000 == 0
            ):
                print(
                    f"Streamed "
                    f"{index:,}/{total_events:,} "
                    f"events"
                )

            time.sleep(
                STREAM_DELAY_SECONDS
            )

        producer.flush()

        print()
        print(
            "Sensor stream completed."
        )

    except KeyboardInterrupt:

        print()
        print(
            "Producer stopped by user."
        )

        producer.flush()


def main():

    print("=" * 60)
    print(
        "COLDGUARD - KAFKA SENSOR PRODUCER"
    )
    print("=" * 60)

    events = load_sensor_events()

    print(
        f"Loaded {len(events):,} sensor events."
    )

    producer = None

    try:

        producer = create_producer()

        print(
            "Connected to Kafka successfully."
        )

        stream_events(
            producer,
            events,
        )

    except KafkaError as error:

        print()
        print(
            "Kafka error:"
        )

        print(error)

        print()
        print(
            "Make sure Kafka is running on:"
        )

        print(
            KAFKA_BOOTSTRAP_SERVERS
        )

    except FileNotFoundError:

        print()
        print(
            "sensor_events.json was not found."
        )

        print(
            f"Expected location:"
        )

        print(
            SENSOR_FILE
        )

    except Exception as error:

        print()
        print(
            "Unexpected error:"
        )

        print(error)

    finally:

        if producer is not None:
            producer.close()

        print()
        print(
            "Producer shut down."
        )


if __name__ == "__main__":
    main()