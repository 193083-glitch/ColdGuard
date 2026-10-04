
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from pymongo import MongoClient


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = "ColdGuard"


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="ColdGuard | Cold-Chain Intelligence",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# DATABASE
# ============================================================

@st.cache_resource
def get_database():
    if not MONGO_URI:
        st.error("MONGO_URI was not found in .env")
        st.stop()

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    return client[DATABASE_NAME]


db = get_database()

products_collection = db["products"]
vehicles_collection = db["vehicles"]
shipments_collection = db["shipments"]
sensor_collection = db["sensor_events"]
alerts_collection = db["alerts"]


# Lightweight indexes used by the dashboard. These make the analytics
# queries much cheaper on MongoDB Atlas Free Tier.
@st.cache_resource
def ensure_dashboard_indexes():
    sensor_collection.create_index([("timestamp", 1)])
    sensor_collection.create_index([("shipment_id", 1)])
    sensor_collection.create_index([("vehicle_id", 1)])
    shipments_collection.create_index([("shipment_id", 1)])
    shipments_collection.create_index([("product_id", 1)])
    products_collection.create_index([("product_id", 1)])
    vehicles_collection.create_index([("vehicle_id", 1)])


ensure_dashboard_indexes()


# ============================================================
# HELPERS
# ============================================================

def money(value):
    if pd.isna(value):
        return "₹0"
    value = float(value)
    if abs(value) >= 10_000_000:
        return f"₹{value / 10_000_000:.2f} Cr"
    if abs(value) >= 100_000:
        return f"₹{value / 100_000:.2f} L"
    return f"₹{value:,.0f}"


def safe_round(df, columns, digits=2):
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column], errors="coerce"
            ).round(digits)
    return df


# ============================================================
# MASTER DATA
# ============================================================

@st.cache_data(ttl=30)
def load_products():
    return pd.DataFrame(
        list(products_collection.find({}, {"_id": 0}))
    )


@st.cache_data(ttl=30)
def load_vehicles():
    return pd.DataFrame(
        list(vehicles_collection.find({}, {"_id": 0}))
    )


@st.cache_data(ttl=30)
def load_shipments():
    return pd.DataFrame(
        list(shipments_collection.find({}, {"_id": 0}))
    )


@st.cache_data(ttl=10)
def load_alerts():
    return pd.DataFrame(
        list(
            alerts_collection.find({}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(10000)
        )
    )


products = load_products()
vehicles = load_vehicles()
shipments = load_shipments()
alerts = load_alerts()


# ============================================================
# STREAMING / ANALYTICS QUERIES
# ============================================================

@st.cache_data(ttl=10)
def load_temperature_trend():
    """
    Show the latest 168 hourly observations without doing a full-collection
    event_id deduplication. The previous deduplication $group had to hold a
    very large working set and exceeded the Atlas memory limit.

    Sensor replay duplicates are small relative to the dataset, so this
    presentation query intentionally prioritizes stable execution on the
    Atlas Free Tier.
    """
    latest = sensor_collection.find_one(
        {"timestamp": {"$exists": True}},
        {"timestamp": 1, "_id": 0},
        sort=[("timestamp", -1)]
    )

    if not latest or not latest.get("timestamp"):
        return pd.DataFrame()

    latest_timestamp = pd.to_datetime(
        latest["timestamp"], utc=True, errors="coerce"
    )
    if pd.isna(latest_timestamp):
        return pd.DataFrame()

    start_timestamp = latest_timestamp - pd.Timedelta(days=7)

    pipeline = [
        {
            "$match": {
                "timestamp": {
                    "$gte": start_timestamp.isoformat().replace("+00:00", "Z"),
                    "$lte": latest["timestamp"]
                }
            }
        },
        {
            "$set": {
                "event_date": {
                    "$convert": {
                        "input": "$timestamp",
                        "to": "date",
                        "onError": None,
                        "onNull": None
                    }
                }
            }
        },
        {"$match": {"event_date": {"$ne": None}}},
        {
            "$group": {
                "_id": {
                    "$dateTrunc": {
                        "date": "$event_date",
                        "unit": "hour"
                    }
                },
                "average_temperature": {"$avg": "$temperature"},
                "maximum_temperature": {"$max": "$temperature"},
                "minimum_temperature": {"$min": "$temperature"},
                "average_ambient": {"$avg": "$ambient_temperature"},
                "events": {"$sum": 1}
            }
        },
        {"$sort": {"_id": -1}},
        {"$limit": 168},
        {"$sort": {"_id": 1}}
    ]

    return pd.DataFrame(list(
        sensor_collection.aggregate(pipeline, allowDiskUse=True)
    ))


@st.cache_data(ttl=15)
def load_route_time_analysis():
    pipeline = [
        {
            "$lookup": {
                "from": "shipments",
                "localField": "shipment_id",
                "foreignField": "shipment_id",
                "as": "shipment"
            }
        },
        {"$unwind": "$shipment"},
        {
            "$lookup": {
                "from": "products",
                "localField": "shipment.product_id",
                "foreignField": "product_id",
                "as": "product"
            }
        },
        {"$unwind": "$product"},
        {
            "$set": {
                "event_date": {
                    "$convert": {
                        "input": "$timestamp",
                        "to": "date",
                        "onError": None,
                        "onNull": None
                    }
                }
            }
        },
        {"$match": {"event_date": {"$ne": None}}},
        {
            "$set": {
                "hour": {"$hour": "$event_date"},
                "route": {
                    "$concat": [
                        "$shipment.origin", " → ",
                        "$shipment.destination"
                    ]
                },
                "temperature_excursion": {
                    "$or": [
                        {"$lt": ["$temperature", "$product.temperature_min"]},
                        {"$gt": ["$temperature", "$product.temperature_max"]}
                    ]
                }
            }
        },
        {
            "$set": {
                "time_period": {
                    "$switch": {
                        "branches": [
                            {
                                "case": {"$and": [
                                    {"$gte": ["$hour", 5]},
                                    {"$lt": ["$hour", 12]}
                                ]},
                                "then": "Morning"
                            },
                            {
                                "case": {"$and": [
                                    {"$gte": ["$hour", 12]},
                                    {"$lt": ["$hour", 17]}
                                ]},
                                "then": "Afternoon"
                            },
                            {
                                "case": {"$and": [
                                    {"$gte": ["$hour", 17]},
                                    {"$lt": ["$hour", 22]}
                                ]},
                                "then": "Evening"
                            }
                        ],
                        "default": "Night"
                    }
                }
            }
        },
        {
            "$group": {
                "_id": {
                    "route": "$route",
                    "time_period": "$time_period"
                },
                "sensor_events": {"$sum": 1},
                "excursions": {
                    "$sum": {"$cond": ["$temperature_excursion", 1, 0]}
                },
                "average_temperature": {"$avg": "$temperature"},
                "maximum_temperature": {"$max": "$temperature"},
                "average_ambient_temperature": {"$avg": "$ambient_temperature"},
                "door_open_events": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$door_status", "OPEN"]},
                            1, 0
                        ]
                    }
                },
                "refrigeration_off_events": {
                    "$sum": {
                        "$cond": [
                            {"$ne": ["$refrigeration_status", "ON"]},
                            1, 0
                        ]
                    }
                },
                "shipments": {"$addToSet": "$shipment_id"}
            }
        },
        {
            "$set": {
                "excursion_rate": {
                    "$multiply": [
                        {"$divide": ["$excursions", "$sensor_events"]},
                        100
                    ]
                },
                "shipment_count": {"$size": "$shipments"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "route": "$_id.route",
                "time_period": "$_id.time_period",
                "sensor_events": 1,
                "excursions": 1,
                "excursion_rate": 1,
                "average_temperature": 1,
                "maximum_temperature": 1,
                "average_ambient_temperature": 1,
                "door_open_events": 1,
                "refrigeration_off_events": 1,
                "shipment_count": 1
            }
        }
    ]

    return pd.DataFrame(list(
        sensor_collection.aggregate(pipeline, allowDiskUse=True)
    ))


@st.cache_data(ttl=15)
def load_category_analysis():
    pipeline = [
        {
            "$lookup": {
                "from": "shipments",
                "localField": "shipment_id",
                "foreignField": "shipment_id",
                "as": "shipment"
            }
        },
        {"$unwind": "$shipment"},
        {
            "$lookup": {
                "from": "products",
                "localField": "shipment.product_id",
                "foreignField": "product_id",
                "as": "product"
            }
        },
        {"$unwind": "$product"},
        {
            "$set": {
                "excursion": {
                    "$or": [
                        {"$lt": ["$temperature", "$product.temperature_min"]},
                        {"$gt": ["$temperature", "$product.temperature_max"]}
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": "$product.category",
                "sensor_events": {"$sum": 1},
                "excursions": {
                    "$sum": {"$cond": ["$excursion", 1, 0]}
                },
                "avg_temperature": {"$avg": "$temperature"},
                "avg_ambient": {"$avg": "$ambient_temperature"},
                "shipment_values": {"$addToSet": "$shipment.shipment_id"}
            }
        },
        {
            "$set": {
                "excursion_rate": {
                    "$multiply": [
                        {"$divide": ["$excursions", "$sensor_events"]},
                        100
                    ]
                },
                "shipment_count": {"$size": "$shipment_values"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "category": "$_id",
                "sensor_events": 1,
                "excursions": 1,
                "excursion_rate": 1,
                "avg_temperature": 1,
                "avg_ambient": 1,
                "shipment_count": 1
            }
        },
        {"$sort": {"excursion_rate": -1}}
    ]

    return pd.DataFrame(list(
        sensor_collection.aggregate(pipeline, allowDiskUse=True)
    ))


@st.cache_data(ttl=15)
def load_vehicle_analysis():
    pipeline = [
        {
            "$lookup": {
                "from": "vehicles",
                "localField": "vehicle_id",
                "foreignField": "vehicle_id",
                "as": "vehicle"
            }
        },
        {"$unwind": "$vehicle"},
        {
            "$lookup": {
                "from": "shipments",
                "localField": "shipment_id",
                "foreignField": "shipment_id",
                "as": "shipment"
            }
        },
        {"$unwind": "$shipment"},
        {
            "$lookup": {
                "from": "products",
                "localField": "shipment.product_id",
                "foreignField": "product_id",
                "as": "product"
            }
        },
        {"$unwind": "$product"},
        {
            "$set": {
                "excursion": {
                    "$or": [
                        {"$lt": ["$temperature", "$product.temperature_min"]},
                        {"$gt": ["$temperature", "$product.temperature_max"]}
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": "$vehicle.vehicle_id",
                "vehicle_type": {"$first": "$vehicle.vehicle_type"},
                "vehicle_age": {
                    "$first": {
                        "$subtract": [
                            {"$year": "$$NOW"},
                            "$vehicle.manufacture_year"
                        ]
                    }
                },
                "efficiency": {
                    "$first": "$vehicle.refrigeration_efficiency"
                },
                "sensor_events": {"$sum": 1},
                "excursions": {
                    "$sum": {"$cond": ["$excursion", 1, 0]}
                },
                "door_open": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$door_status", "OPEN"]},
                            1, 0
                        ]
                    }
                },
                "refrigeration_off": {
                    "$sum": {
                        "$cond": [
                            {"$ne": ["$refrigeration_status", "ON"]},
                            1, 0
                        ]
                    }
                }
            }
        },
        {
            "$set": {
                "excursion_rate": {
                    "$multiply": [
                        {"$divide": ["$excursions", "$sensor_events"]},
                        100
                    ]
                }
            }
        },
        {"$match": {"sensor_events": {"$gte": 20}}},
        {
            "$project": {
                "_id": 0,
                "vehicle_id": "$_id",
                "vehicle_type": 1,
                "vehicle_age": 1,
                "efficiency": 1,
                "sensor_events": 1,
                "excursions": 1,
                "excursion_rate": 1,
                "door_open": 1,
                "refrigeration_off": 1
            }
        },
        {"$sort": {"excursion_rate": -1}},
        {"$limit": 20}
    ]

    return pd.DataFrame(list(
        sensor_collection.aggregate(pipeline, allowDiskUse=True)
    ))


@st.cache_data(ttl=15)
def load_delay_analysis():
    pipeline = [
        {
            "$set": {
                "expected": {
                    "$convert": {
                        "input": "$expected_arrival",
                        "to": "date",
                        "onError": None,
                        "onNull": None
                    }
                },
                "actual": {
                    "$convert": {
                        "input": "$actual_arrival",
                        "to": "date",
                        "onError": None,
                        "onNull": None
                    }
                }
            }
        },
        {
            "$set": {
                "delay_hours": {
                    "$divide": [
                        {"$subtract": ["$actual", "$expected"]},
                        3600000
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": {
                    "$cond": [
                        {"$lte": ["$delay_hours", 0]},
                        "On time / early",
                        {
                            "$cond": [
                                {"$lt": ["$delay_hours", 2]},
                                "0–2 hours late",
                                {
                                    "$cond": [
                                        {"$lt": ["$delay_hours", 4]},
                                        "2–4 hours late",
                                        "4+ hours late"
                                    ]
                                }
                            ]
                        }
                    ]
                },
                "shipments": {"$sum": 1},
                "avg_delay_hours": {"$avg": "$delay_hours"},
                "inventory_value": {"$sum": "$shipment_value"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "delay_group": "$_id",
                "shipments": 1,
                "avg_delay_hours": 1,
                "inventory_value": 1
            }
        }
    ]

    return pd.DataFrame(list(
        shipments_collection.aggregate(pipeline, allowDiskUse=True)
    ))


# ============================================================
# HEADER / SIDEBAR
# ============================================================

st.title("❄️ ColdGuard")
st.subheader("Real-Time Cold-Chain Risk Intelligence")

st.markdown(
    """
    **ColdGuard** combines streaming sensor observations with product,
    shipment, and vehicle context to identify temperature risk and
    investigate the conditions behind it.
    """
)

with st.sidebar:
    st.header("Dashboard Controls")

    if st.button("🔄 Refresh live data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption(
        "The dashboard reads the existing MongoDB Atlas data. "
        "No source documents are modified."
    )

    st.divider()
    st.markdown("### Analytical dimensions")
    st.markdown(
        """
        - Route
        - Time of day
        - Product category
        - Vehicle
        - Ambient conditions
        - Door status
        - Refrigeration status
        - Shipment delay
        """
    )


# ============================================================
# BASIC DATA PREPARATION
# ============================================================

if not alerts.empty:
    alerts["timestamp"] = pd.to_datetime(
        alerts["timestamp"], errors="coerce"
    )

if not shipments.empty:
    for field in ["departure_time", "expected_arrival", "actual_arrival"]:
        if field in shipments.columns:
            shipments[field] = pd.to_datetime(
                shipments[field], errors="coerce"
            )


# ============================================================
# EXECUTIVE KPIs
# ============================================================

total_shipments = len(shipments)
total_vehicles = len(vehicles)
sensor_count = int(sensor_collection.count_documents({}))

open_alerts = 0
high_alerts = 0
critical_alerts = 0
inventory_at_risk = 0

if not alerts.empty:
    open_alerts = int(
        (alerts.get("status", pd.Series(dtype=str)) == "OPEN").sum()
    )
    high_alerts = int(
        (alerts.get("severity", pd.Series(dtype=str)) == "HIGH").sum()
    )
    critical_alerts = int(
        (alerts.get("severity", pd.Series(dtype=str)) == "CRITICAL").sum()
    )
    if "inventory_value_at_risk" in alerts.columns:
        inventory_at_risk = alerts[
            "inventory_value_at_risk"
        ].fillna(0).sum()

st.divider()

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Shipments", f"{total_shipments:,}")
k2.metric("Vehicles", f"{total_vehicles:,}")
k3.metric("Sensor Events", f"{sensor_count:,}")
k4.metric("Open Alerts", f"{open_alerts:,}")
k5.metric("High / Critical", f"{high_alerts + critical_alerts:,}")
k6.metric("Value at Risk", money(inventory_at_risk))


# ============================================================
# 1. TEMPERATURE / AMBIENT TREND
# ============================================================

st.divider()
st.header("🌡️ Temperature & Environmental Trend")

trend = load_temperature_trend()

if not trend.empty:
    trend = trend.rename(columns={"_id": "timestamp"})
    trend["timestamp"] = pd.to_datetime(
        trend["timestamp"], errors="coerce"
    )
    trend = trend.sort_values("timestamp").tail(168)

    fig = px.line(
        trend,
        x="timestamp",
        y=["average_temperature", "average_ambient"],
        labels={
            "timestamp": "Time",
            "value": "Temperature (°C)",
            "variable": "Measurement"
        },
        title="Hourly Average Product-Sensor Temperature vs Ambient Temperature"
    )
    fig.update_layout(height=430, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "This compares the transported product environment with ambient "
        "conditions. A temperature excursion is a risk signal, not proof "
        "of product spoilage."
    )
else:
    st.info("No valid timestamped sensor data is available.")


# ============================================================
# 2. ROUTE × TIME OF DAY
# ============================================================

st.divider()
st.header("🔎 Route × Time-of-Day Intelligence")

st.markdown(
    """
    **Question:** Does the same route show different temperature-excursion
    behaviour depending on when the shipment travels?
    """
)

route_data = load_route_time_analysis()

if not route_data.empty:
    routes = sorted(route_data["route"].dropna().unique())
    selected_route = st.selectbox(
        "Choose a route",
        routes,
        key="route_selector"
    )

    selected = route_data[
        route_data["route"] == selected_route
    ].copy()

    period_order = ["Morning", "Afternoon", "Evening", "Night"]
    selected["time_period"] = pd.Categorical(
        selected["time_period"],
        categories=period_order,
        ordered=True
    )
    selected = selected.sort_values("time_period")

    fig = px.bar(
        selected,
        x="time_period",
        y="excursion_rate",
        text="excursion_rate",
        title=f"Temperature Excursion Rate — {selected_route}",
        labels={
            "time_period": "Time of Day",
            "excursion_rate": "Excursion Rate (%)"
        }
    )
    fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

    detail = selected[
        [
            "time_period",
            "shipment_count",
            "sensor_events",
            "excursions",
            "excursion_rate",
            "average_temperature",
            "maximum_temperature",
            "average_ambient_temperature",
            "door_open_events",
            "refrigeration_off_events"
        ]
    ].copy()

    detail.columns = [
        "Time",
        "Shipments",
        "Sensor Events",
        "Excursions",
        "Excursion Rate (%)",
        "Avg Temp (°C)",
        "Max Temp (°C)",
        "Avg Ambient (°C)",
        "Door Open Events",
        "Refrigeration Off"
    ]

    detail = safe_round(
        detail,
        [
            "Excursion Rate (%)",
            "Avg Temp (°C)",
            "Max Temp (°C)",
            "Avg Ambient (°C)"
        ]
    )

    st.dataframe(
        detail,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Route-time analysis could not be calculated.")


# ============================================================
# 3. PRODUCT CATEGORY
# ============================================================

st.divider()
st.header("📦 Product Category Risk")

category_data = load_category_analysis()

if not category_data.empty:
    fig = px.bar(
        category_data.sort_values("excursion_rate", ascending=False),
        x="category",
        y="excursion_rate",
        text="excursion_rate",
        title="Temperature Excursion Rate by Product Category",
        labels={
            "category": "Product Category",
            "excursion_rate": "Excursion Rate (%)"
        }
    )
    fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

    cat_table = category_data[
        [
            "category",
            "shipment_count",
            "sensor_events",
            "excursions",
            "excursion_rate",
            "avg_temperature",
            "avg_ambient"
        ]
    ].copy()

    cat_table.columns = [
        "Category",
        "Shipments",
        "Sensor Events",
        "Excursions",
        "Excursion Rate (%)",
        "Avg Temp (°C)",
        "Avg Ambient (°C)"
    ]

    cat_table = safe_round(
        cat_table,
        [
            "Excursion Rate (%)",
            "Avg Temp (°C)",
            "Avg Ambient (°C)"
        ]
    )

    st.dataframe(
        cat_table,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# 4. VEHICLE PERFORMANCE
# ============================================================

st.divider()
st.header("🚚 Vehicle Performance & Repeated Risk")

vehicle_data = load_vehicle_analysis()

if not vehicle_data.empty:
    fig = px.bar(
        vehicle_data.sort_values("excursion_rate"),
        x="excursion_rate",
        y="vehicle_id",
        orientation="h",
        title="Vehicles with Highest Observed Temperature-Excursion Rates",
        labels={
            "vehicle_id": "Vehicle",
            "excursion_rate": "Excursion Rate (%)"
        },
        hover_data=[
            "vehicle_age",
            "efficiency",
            "sensor_events",
            "excursions",
            "door_open",
            "refrigeration_off"
        ]
    )
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Vehicles are shown only when they have at least 20 unique sensor "
        "events in the available dataset, reducing misleading results from "
        "very small samples."
    )

    vehicle_table = vehicle_data.copy()
    vehicle_table.columns = [
        "Vehicle",
        "Type",
        "Age (years)",
        "Refrigeration Efficiency",
        "Sensor Events",
        "Excursions",
        "Excursion Rate (%)",
        "Door Open",
        "Refrigeration Off"
    ]

    vehicle_table = safe_round(
        vehicle_table,
        ["Refrigeration Efficiency", "Excursion Rate (%)"]
    )

    st.dataframe(
        vehicle_table,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# 5. SHIPMENT DELAY × BUSINESS EXPOSURE
# ============================================================

st.divider()
st.header("⏱️ Shipment Delay & Inventory Exposure")

delay_data = load_delay_analysis()

if not delay_data.empty:
    order = [
        "On time / early",
        "0–2 hours late",
        "2–4 hours late",
        "4+ hours late"
    ]

    delay_data["delay_group"] = pd.Categorical(
        delay_data["delay_group"],
        categories=order,
        ordered=True
    )
    delay_data = delay_data.sort_values("delay_group")

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(
            delay_data,
            x="delay_group",
            y="shipments",
            title="Shipments by Arrival Delay",
            labels={
                "delay_group": "Arrival Delay",
                "shipments": "Shipments"
            }
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(
            delay_data,
            x="delay_group",
            y="inventory_value",
            title="Shipment Value by Delay Group",
            labels={
                "delay_group": "Arrival Delay",
                "inventory_value": "Shipment Value (₹)"
            }
        )
        st.plotly_chart(fig, use_container_width=True)

    delay_table = delay_data[
        [
            "delay_group",
            "shipments",
            "avg_delay_hours",
            "inventory_value"
        ]
    ].copy()

    delay_table.columns = [
        "Delay Group",
        "Shipments",
        "Average Delay (hours)",
        "Shipment Value (₹)"
    ]

    delay_table = safe_round(
        delay_table,
        ["Average Delay (hours)", "Shipment Value (₹)"]
    )

    st.dataframe(
        delay_table,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# 6. OPERATING CONDITIONS / ROOT-CAUSE SIGNALS
# ============================================================

st.divider()
st.header("🧩 Operating Conditions Behind Temperature Risk")

if not route_data.empty:
    root_summary = pd.DataFrame({
        "Condition": [
            "Door Open Events",
            "Refrigeration Off Events",
            "Temperature Excursions"
        ],
        "Events": [
            int(route_data["door_open_events"].sum()),
            int(route_data["refrigeration_off_events"].sum()),
            int(route_data["excursions"].sum())
        ]
    })

    fig = px.bar(
        root_summary,
        x="Condition",
        y="Events",
        title="Observed Operating Conditions in the Route-Time Dataset",
        labels={
            "Condition": "Condition",
            "Events": "Observed Events"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "These are observed signals used for investigation; they are not "
        "proof of a single root cause."
    )


# ============================================================
# 7. ALERT INTELLIGENCE
# ============================================================

st.divider()
st.header("🚨 Alert Intelligence")

if not alerts.empty:
    col1, col2 = st.columns(2)

    with col1:
        severity_counts = (
            alerts["severity"]
            .value_counts()
            .rename_axis("severity")
            .reset_index(name="count")
        )

        fig = px.bar(
            severity_counts,
            x="severity",
            y="count",
            title="Alerts by Severity",
            labels={
                "severity": "Severity",
                "count": "Alerts"
            }
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        cause_counts = (
            alerts["probable_cause"]
            .value_counts()
            .rename_axis("probable_cause")
            .reset_index(name="count")
        )

        fig = px.bar(
            cause_counts,
            x="count",
            y="probable_cause",
            orientation="h",
            title="Alerts by Probable Cause",
            labels={
                "probable_cause": "Probable Cause",
                "count": "Alerts"
            }
        )
        st.plotly_chart(fig, use_container_width=True)

    alert_table = alerts.copy()

    display_columns = [
        "timestamp",
        "shipment_id",
        "vehicle_id",
        "product_id",
        "severity",
        "risk_score",
        "probable_cause",
        "temperature",
        "threshold_min",
        "threshold_max",
        "inventory_value_at_risk",
        "status"
    ]

    display_columns = [
        c for c in display_columns
        if c in alert_table.columns
    ]

    alert_table = alert_table[display_columns].head(25)

    if "inventory_value_at_risk" in alert_table.columns:
        alert_table["inventory_value_at_risk"] = (
            alert_table["inventory_value_at_risk"].apply(money)
        )

    st.dataframe(
        alert_table,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info(
        "No alerts are currently stored. The alert section will populate "
        "as the streaming risk engine generates alerts."
    )


# ============================================================
# 8. PIPELINE STATUS
# ============================================================

st.divider()
st.header("⚡ Streaming Pipeline Status")

status1, status2, status3, status4 = st.columns(4)
status1.metric("Kafka Topic", "coldchain.sensor.events")
status2.metric("Storage", "MongoDB Atlas")
status3.metric("Risk Engine", "Python")
status4.metric("Dashboard", "Streamlit")

st.markdown(
    """
    **Analytical flow**

    `Sensor event → Shipment → Product rules → Vehicle context → Risk indicators → Dashboard`

    The dashboard derives analytical relationships from the existing five
    collections. It does not add labels such as “rotting” to the dataset.
    A temperature excursion is treated as a **risk signal**, not proof of
    product spoilage.
    """
)

st.caption(
    "ColdGuard • Streaming Data Analytics Project • "
    "Kafka → Python Risk Engine → MongoDB Atlas → Streamlit"
)
