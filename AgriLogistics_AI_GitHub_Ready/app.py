import heapq
import random
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

st.set_page_config(page_title="AgriLogistics AI", page_icon="🚚", layout="wide")

# Demonstration network only. Distances, travel times, traffic and road
# conditions are illustrative and must be replaced with verified route data.
NODES = {
    "Kano": (12.0022, 8.5920), "Kaduna": (10.5105, 7.4165),
    "Zaria": (11.0855, 7.7199), "Jos": (9.8965, 8.8583),
    "Abuja": (9.0765, 7.3986), "Lokoja": (7.8023, 6.7430),
    "Ilorin": (8.4966, 4.5421), "Ibadan": (7.3775, 3.9470),
    "Lagos": (6.5244, 3.3792), "Benin City": (6.3350, 5.6037),
    "Onitsha": (6.1667, 6.7833), "Port Harcourt": (4.8156, 7.0498),
}
EDGES = [
    ("Kano", "Kaduna", 190, 2.8, "Fair", "Medium"),
    ("Kano", "Zaria", 75, 1.2, "Fair", "Low"),
    ("Zaria", "Kaduna", 75, 1.2, "Good", "Medium"),
    ("Kaduna", "Abuja", 185, 2.8, "Fair", "Medium"),
    ("Kaduna", "Jos", 220, 3.8, "Fair", "Low"),
    ("Jos", "Abuja", 280, 4.4, "Fair", "Medium"),
    ("Abuja", "Lokoja", 190, 3.0, "Fair", "Medium"),
    ("Lokoja", "Ilorin", 220, 3.6, "Fair", "Low"),
    ("Ilorin", "Ibadan", 160, 2.5, "Good", "Medium"),
    ("Ibadan", "Lagos", 130, 2.3, "Good", "High"),
    ("Lokoja", "Benin City", 210, 3.6, "Fair", "Medium"),
    ("Benin City", "Ibadan", 250, 4.0, "Fair", "Medium"),
    ("Benin City", "Onitsha", 115, 2.0, "Fair", "High"),
    ("Onitsha", "Port Harcourt", 150, 2.7, "Fair", "Medium"),
    ("Lagos", "Benin City", 300, 4.8, "Fair", "High"),
]
ROAD_FACTOR = {"Good": 1.0, "Fair": 1.18, "Poor": 1.45}
TRAFFIC_FACTOR = {"Low": 1.0, "Medium": 1.18, "High": 1.45}

DEFAULT_FLEET = pd.DataFrame([
    {"vehicle_id": "REF-001", "vehicle_type": "Refrigerated truck", "capacity_kg": 8000, "refrigeration_type": "Chilled", "min_temp_c": 8, "max_temp_c": 15, "maintenance_score": 92, "maintenance_events_12m": 1, "last_service_date": "2026-08-10", "available": True},
    {"vehicle_id": "REF-002", "vehicle_type": "Refrigerated van", "capacity_kg": 2500, "refrigeration_type": "Chilled", "min_temp_c": 7, "max_temp_c": 14, "maintenance_score": 88, "maintenance_events_12m": 2, "last_service_date": "2026-07-22", "available": True},
    {"vehicle_id": "FRO-003", "vehicle_type": "Refrigerated truck", "capacity_kg": 10000, "refrigeration_type": "Frozen", "min_temp_c": -18, "max_temp_c": -5, "maintenance_score": 90, "maintenance_events_12m": 1, "last_service_date": "2026-09-01", "available": True},
    {"vehicle_id": "INS-004", "vehicle_type": "Insulated truck", "capacity_kg": 5000, "refrigeration_type": "Insulated", "min_temp_c": 10, "max_temp_c": 25, "maintenance_score": 82, "maintenance_events_12m": 3, "last_service_date": "2026-05-18", "available": True},
    {"vehicle_id": "OPEN-005", "vehicle_type": "Open truck", "capacity_kg": 6000, "refrigeration_type": "None", "min_temp_c": 20, "max_temp_c": 40, "maintenance_score": 75, "maintenance_events_12m": 4, "last_service_date": "2026-04-12", "available": True},
    {"vehicle_id": "REF-006", "vehicle_type": "Refrigerated van", "capacity_kg": 1800, "refrigeration_type": "Chilled", "min_temp_c": 7, "max_temp_c": 14, "maintenance_score": 65, "maintenance_events_12m": 5, "last_service_date": "2026-02-11", "available": False},
])

# Illustrative planning values only. Confirm commodity-specific conditions with
# authoritative post-harvest guidance before any real shipment is planned.
# Each record: temperature min/max °C, relative humidity min/max %, oxygen min/max %.
COMMODITIES = {
    "Tomatoes": (10, 15, 85, 95, 19, 21),
    "Pepper": (7, 12, 85, 95, 19, 21),
    "Citrus fruits": (4, 10, 85, 95, 19, 21),
    "Mango": (10, 13, 85, 95, 19, 21),
    "Pineapple": (7, 10, 85, 95, 19, 21),
    "Banana": (13, 14, 85, 95, 19, 21),
    "Plantain": (12, 14, 85, 95, 19, 21),
    "Strawberry": (0, 4, 90, 95, 19, 21),
    "Watermelon": (10, 15, 85, 95, 19, 21),
    "Pawpaw (Papaya)": (7, 13, 85, 95, 19, 21),
    "Avocado": (5, 13, 85, 95, 19, 21),
    "Grapes": (0, 4, 90, 95, 19, 21),
    "Carrot": (0, 4, 90, 95, 19, 21),
    "Cabbage": (0, 5, 90, 95, 19, 21),
    "Lettuce": (0, 4, 90, 95, 19, 21),
    "Spinach": (0, 4, 90, 95, 19, 21),
    "Cucumber": (10, 13, 85, 95, 19, 21),
    "Garden egg": (8, 12, 85, 95, 19, 21),
    "Okra": (7, 10, 85, 95, 19, 21),
    "Fresh cassava roots": (5, 10, 85, 95, 19, 21),
}


def validate_fleet(df):
    required = {
        "vehicle_id", "vehicle_type", "capacity_kg", "refrigeration_type",
        "min_temp_c", "max_temp_c", "maintenance_score",
        "maintenance_events_12m", "last_service_date", "available"
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError("Fleet file is missing columns: " + ", ".join(sorted(missing)))
    out = df.copy()
    numeric_cols = ["capacity_kg", "min_temp_c", "max_temp_c", "maintenance_score", "maintenance_events_12m"]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if out[numeric_cols].isna().any().any():
        raise ValueError("Fleet numeric fields contain blank or invalid values.")
    if (out["capacity_kg"] <= 0).any() or (out["min_temp_c"] > out["max_temp_c"]).any():
        raise ValueError("Capacities must be positive and minimum temperatures must not exceed maximum temperatures.")
    if ((out["maintenance_score"] < 0) | (out["maintenance_score"] > 100)).any():
        raise ValueError("Maintenance scores must be between 0 and 100.")
    if (out["maintenance_events_12m"] < 0).any():
        raise ValueError("Maintenance event counts cannot be negative.")
    out["available"] = out["available"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "available"])
    out["last_service_date"] = pd.to_datetime(out["last_service_date"], errors="coerce")
    return out


def vehicle_ranking(fleet, load_kg, target_min, target_max):
    """Transparent rule-based scoring; not a trained machine-learning model."""
    rows = []
    required_span = max(0.1, float(target_max) - float(target_min))
    today = pd.Timestamp.today().normalize()
    for _, vehicle in fleet.iterrows():
        vmin, vmax = float(vehicle.min_temp_c), float(vehicle.max_temp_c)
        overlap = max(0.0, min(vmax, target_max) - max(vmin, target_min))
        temperature_coverage = min(1.0, overlap / required_span)
        fully_covers = vmin <= target_min and vmax >= target_max
        capacity = float(vehicle.capacity_kg)
        utilization = float(load_kg) / capacity
        # Prefer a vehicle that can carry the load without being overloaded,
        # while avoiding a very poor capacity fit where alternatives exist.
        capacity_fit = max(0.0, min(1.0, 1.0 - abs(0.70 - min(utilization, 1.0)) / 0.70))
        maintenance = max(0.0, min(100.0, float(vehicle.maintenance_score)))
        events = max(0.0, float(vehicle.maintenance_events_12m))
        service_date = vehicle.last_service_date
        if pd.isna(service_date):
            service_recency = 35.0
            service_age_days = None
        else:
            service_age_days = max(0, (today - service_date.normalize()).days)
            service_recency = max(0.0, 100.0 - (service_age_days / 365.0) * 100.0)
        history_score = max(0.0, 100.0 - events * 12.0)

        score = (
            45.0 * temperature_coverage
            + 20.0 * capacity_fit
            + 15.0 * (maintenance / 100.0)
            + 10.0 * (service_recency / 100.0)
            + 10.0 * (history_score / 100.0)
        )
        reasons = []
        if not bool(vehicle.available):
            reasons.append("Vehicle unavailable")
        if capacity < load_kg:
            reasons.append("Insufficient payload capacity")
        if temperature_coverage < 0.70:
            reasons.append("Temperature range covers less than 70% of the requested range")
        if maintenance < 50:
            reasons.append("Maintenance score is below the recommended screening threshold")
        eligible = not reasons
        if fully_covers:
            temp_note = "Full temperature-range coverage"
        else:
            temp_note = f"Partial temperature coverage ({temperature_coverage * 100:.1f}%)"
        rows.append({
            "Vehicle ID": str(vehicle.vehicle_id),
            "Vehicle type": str(vehicle.vehicle_type),
            "Capacity (kg)": int(capacity),
            "Load utilisation (%)": round(utilization * 100, 1),
            "Refrigeration": str(vehicle.refrigeration_type),
            "Temperature range (°C)": f"{vmin:g} to {vmax:g}",
            "Temperature coverage (%)": round(temperature_coverage * 100, 1),
            "Temperature assessment": temp_note,
            "Maintenance score": round(maintenance, 1),
            "Maintenance events (12 months)": int(events),
            "Days since service": service_age_days if service_age_days is not None else "Unknown",
            "Last service": service_date.strftime("%Y-%m-%d") if pd.notna(service_date) else "Not recorded",
            "Available": bool(vehicle.available),
            "Recommendation score": round(score, 1),
            "Eligible": eligible,
            "Decision": "Suitable" if eligible else "; ".join(reasons),
        })
    return pd.DataFrame(rows).sort_values(["Eligible", "Recommendation score"], ascending=[False, False]).reset_index(drop=True)


def edge_time(edge):
    _, _, _, base_hours, road, traffic = edge
    return base_hours * ROAD_FACTOR[road] * TRAFFIC_FACTOR[traffic]


def find_route(start, goal, target_min, target_max, ambient_temp, vehicle_type, weights):
    graph = {node: [] for node in NODES}
    info = {}
    for edge in EDGES:
        a, b, km, _, road, traffic = edge
        hours = edge_time(edge)
        deviation = max(0.0, target_min - ambient_temp, ambient_temp - target_max)
        vehicle_buffer = {
            "Refrigerated truck": 0.25, "Refrigerated van": 0.30,
            "Insulated truck": 0.55, "Open truck": 1.0,
        }.get(vehicle_type, 0.7)
        exposure = hours * deviation * vehicle_buffer
        info[(a, b)] = {"km": km, "hours": hours, "road": road, "traffic": traffic, "exposure": exposure}
        info[(b, a)] = info[(a, b)]
        graph[a].append(b)
        graph[b].append(a)

    def dijkstra(distance_only=False):
        queue = [(0.0, start, [start])]
        best = {start: 0.0}
        while queue:
            cost, node, path = heapq.heappop(queue)
            if node == goal:
                legs = [info[(path[i], path[i + 1])] for i in range(len(path) - 1)]
                return path, legs
            if cost > best.get(node, float("inf")):
                continue
            for nxt in graph[node]:
                leg = info[(node, nxt)]
                weight = leg["km"] if distance_only else (
                    weights[0] * (leg["km"] / 100.0)
                    + weights[1] * leg["hours"]
                    + weights[2] * leg["exposure"]
                )
                new_cost = cost + weight
                if new_cost < best.get(nxt, float("inf")):
                    best[nxt] = new_cost
                    heapq.heappush(queue, (new_cost, nxt, path + [nxt]))
        return [], []

    return dijkstra(True), dijkstra(False)


def summarize(path, legs):
    return {
        "path": path,
        "distance_km": sum(leg["km"] for leg in legs),
        "hours": sum(leg["hours"] for leg in legs),
        "exposure_proxy": sum(leg["exposure"] for leg in legs),
        "legs": legs,
    }


def simulate_iot(hours, target_min, target_max, vehicle_type, humidity_min, humidity_max,
                 oxygen_min, oxygen_max, seed=12):
    rng = random.Random(seed)
    count = max(2, min(72, int(round(hours)) + 1))
    start_time = datetime.now().replace(microsecond=0)
    temp_mid = (target_min + target_max) / 2
    humidity_mid = (humidity_min + humidity_max) / 2
    oxygen_mid = (oxygen_min + oxygen_max) / 2
    variation = {
        "Refrigerated truck": 0.7, "Refrigerated van": 1.0,
        "Insulated truck": 2.0, "Open truck": 4.0,
    }.get(vehicle_type, 2.5)
    records = []
    for hour in range(count):
        temperature = temp_mid + rng.uniform(-variation, variation)
        humidity = humidity_mid + rng.uniform(-5.0, 5.0)
        oxygen = oxygen_mid + rng.uniform(-0.8, 0.8)
        battery = max(5, 100 - hour * rng.uniform(0.15, 0.65))
        signal = rng.choice(["Good", "Good", "Good", "Fair", "Weak"])
        sensor_status = "Online" if rng.random() > 0.06 else "Intermittent"
        temp_alert = not (target_min <= temperature <= target_max)
        humidity_alert = not (humidity_min <= humidity <= humidity_max)
        oxygen_alert = not (oxygen_min <= oxygen <= oxygen_max)
        alerts = []
        if temp_alert:
            alerts.append("Temperature")
        if humidity_alert:
            alerts.append("Humidity")
        if oxygen_alert:
            alerts.append("Oxygen")
        if sensor_status != "Online":
            alerts.append("Sensor connection")
        records.append({
            "Timestamp": start_time + timedelta(hours=hour),
            "Trip hour": hour,
            "Simulated temperature (°C)": round(temperature, 1),
            "Simulated relative humidity (%)": round(humidity, 1),
            "Simulated oxygen (%)": round(oxygen, 1),
            "Sensor status": sensor_status,
            "Signal strength": signal,
            "Battery (%)": round(battery, 1),
            "Temperature alert": temp_alert,
            "Humidity alert": humidity_alert,
            "Oxygen alert": oxygen_alert,
            "Alert details": ", ".join(alerts) if alerts else "None",
        })
    return pd.DataFrame(records)


st.title("🚚 AgriLogistics AI")
st.caption("Vehicle recommendation and route optimization for perishable agricultural commodities in Nigerian trade corridors")
st.info(
    "Prototype notice: route distances, traffic, road conditions, fleet records, commodity limits and all IoT readings are illustrative. "
    "The IoT dashboard uses simulated data, not physical sensors or live telemetry. This prototype does not provide live GPS, verified spoilage estimates or dispatch instructions."
)

with st.sidebar:
    st.header("Shipment details")
    commodity = st.selectbox("Commodity", list(COMMODITIES))
    default_min, default_max, default_hmin, default_hmax, default_omin, default_omax = COMMODITIES[commodity]
    st.caption("The following commodity ranges are demonstration defaults, not validated handling specifications.")
    target_min = st.number_input("Required cargo temperature minimum (°C)", value=float(default_min), step=0.5)
    target_max = st.number_input("Required cargo temperature maximum (°C)", value=float(default_max), step=0.5)
    humidity_min = st.number_input("Relative humidity minimum (%)", min_value=0.0, max_value=100.0, value=float(default_hmin), step=1.0)
    humidity_max = st.number_input("Relative humidity maximum (%)", min_value=0.0, max_value=100.0, value=float(default_hmax), step=1.0)
    oxygen_min = st.number_input("Oxygen minimum (%)", min_value=0.0, max_value=100.0, value=float(default_omin), step=0.5)
    oxygen_max = st.number_input("Oxygen maximum (%)", min_value=0.0, max_value=100.0, value=float(default_omax), step=0.5)
    valid_limits = target_min < target_max and humidity_min < humidity_max and oxygen_min < oxygen_max
    if not valid_limits:
        st.error("For each monitoring range, the maximum must be greater than the minimum.")
    load = st.number_input("Cargo weight (kg)", min_value=1, max_value=30000, value=2000, step=100)
    origin = st.selectbox("Origin", list(NODES), index=list(NODES).index("Kano"))
    destinations = [node for node in NODES if node != origin]
    destination = st.selectbox("Destination", destinations, index=destinations.index("Lagos") if "Lagos" in destinations else 0)
    ambient = st.number_input("Assumed average ambient temperature (°C)", value=30.0, step=0.5)

if not valid_limits:
    st.warning("Correct the monitoring ranges in the sidebar before using shipment calculations.")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Vehicle recommendation", "Route comparison", "Simulated IoT monitoring"])

with tab1:
    st.subheader("Shipment planning")
    c1, c2, c3 = st.columns(3)
    c1.metric("Commodity", commodity)
    c2.metric("Cargo weight", f"{load:,.0f} kg")
    c3.metric("Cargo temperature range", f"{target_min:g}–{target_max:g} °C")
    st.write("The prototype combines vehicle suitability screening, route comparison and simulated multi-sensor cargo monitoring.")
    st.markdown("**Workflow**")
    st.write("1. Enter cargo and shipment details in the sidebar.")
    st.write("2. Review eligible vehicles using temperature compatibility, payload, maintenance condition and service history.")
    st.write("3. Compare the shortest-distance route with the weighted route.")
    st.write("4. Review simulated temperature, humidity, oxygen and sensor-status readings.")
    st.metric("Perishable commodities available", len(COMMODITIES))

with tab2:
    st.subheader("Vehicle recommendation engine")
    uploaded = st.file_uploader("Optional: upload your fleet CSV", type=["csv"], key="fleet_csv")
    try:
        fleet = validate_fleet(pd.read_csv(uploaded) if uploaded is not None else DEFAULT_FLEET)
        ranked = vehicle_ranking(fleet, load, target_min, target_max)
        eligible = ranked[ranked["Eligible"]]
        if not eligible.empty:
            best = eligible.iloc[0]
            st.success(
                f"Top recommended vehicle: {best['Vehicle ID']} — {best['Vehicle type']} "
                f"(score {best['Recommendation score']}/100)"
            )
            st.session_state["selected_vehicle"] = best["Vehicle type"]
            st.write(
                f"Recommendation basis: {best['Temperature assessment'].lower()}, "
                f"{best['Load utilisation (%)']}% load utilisation, maintenance score "
                f"{best['Maintenance score']}/100, and {best['Days since service']} days since service."
            )
        else:
            st.error("No vehicle passes all eligibility checks. Review the cargo requirements, load weight or fleet records.")
            st.session_state["selected_vehicle"] = "Refrigerated truck"
        st.dataframe(ranked, use_container_width=True, hide_index=True)
        st.caption(
            "Scoring is a transparent rule-based decision aid, not a trained AI prediction. "
            "Temperature coverage and payload are prioritised, with maintenance condition, service recency and repair-event history also considered."
        )
        st.download_button("Download vehicle ranking CSV", ranked.to_csv(index=False), "vehicle_recommendations.csv", "text/csv")
        st.download_button("Download fleet CSV", fleet.to_csv(index=False), "vehicle_fleet.csv", "text/csv")
    except Exception as exc:
        st.error(f"Fleet data could not be processed: {exc}")
        st.caption("Check that the uploaded CSV contains all required fleet columns and valid values.")

with tab3:
    st.subheader("Distance-only versus perishability-aware route")
    w1, w2, w3 = st.columns(3)
    distance_weight = w1.slider("Distance importance", 0.0, 5.0, 2.0, 0.1)
    time_weight = w2.slider("Travel-time importance", 0.0, 5.0, 2.0, 0.1)
    exposure_weight = w3.slider("Temperature-exposure importance", 0.0, 5.0, 2.0, 0.1)
    selected_type = st.session_state.get("selected_vehicle", "Refrigerated truck")
    (base_path, base_legs), (opt_path, opt_legs) = find_route(
        origin, destination, target_min, target_max, ambient, selected_type,
        (distance_weight, time_weight, exposure_weight)
    )
    if base_path and opt_path:
        base_summary = summarize(base_path, base_legs)
        opt_summary = summarize(opt_path, opt_legs)
        st.write(f"**Distance-only route:** {' → '.join(base_path)}")
        st.write(f"**Weighted route:** {' → '.join(opt_path)}")
        comparison = []
        for label, summary in [("Distance-only", base_summary), ("Weighted route", opt_summary)]:
            comparison.append({
                "Route": label,
                "Distance (km)": round(summary["distance_km"], 1),
                "Estimated hours": round(summary["hours"], 2),
                "Temperature-exposure proxy": round(summary["exposure_proxy"], 2),
            })
        st.dataframe(pd.DataFrame(comparison), use_container_width=True, hide_index=True)
        if base_summary["hours"] > 0:
            st.metric(
                "Estimated time difference",
                f"{base_summary['hours'] - opt_summary['hours']:+.2f} hours",
                help="Positive means the weighted route is faster under the illustrative assumptions."
            )
        st.caption(
            "The route engine uses Dijkstra's algorithm. Its exposure proxy is a simplified temperature-deviation indicator "
            "multiplied by estimated trip time and a vehicle-type factor; it is not a validated spoilage estimate."
        )
        st.markdown("**Weighted route segments**")
        legs_df = pd.DataFrame([
            {"From": opt_path[i], "To": opt_path[i + 1], "Distance (km)": leg["km"],
             "Estimated hours": round(leg["hours"], 2), "Road condition": leg["road"],
             "Traffic assumption": leg["traffic"], "Exposure proxy": round(leg["exposure"], 2)}
            for i, leg in enumerate(opt_legs)
        ])
        st.dataframe(legs_df, use_container_width=True, hide_index=True)
        st.map(pd.DataFrame([{"lat": NODES[node][0], "lon": NODES[node][1]} for node in opt_path]), latitude="lat", longitude="lon")
        st.download_button("Download route comparison CSV", pd.DataFrame(comparison).to_csv(index=False), "route_comparison.csv", "text/csv")
        st.download_button("Download route segments CSV", legs_df.to_csv(index=False), "route_segments.csv", "text/csv")
        st.session_state["route_summary"] = opt_summary
        st.session_state["route_vehicle_type"] = selected_type
    else:
        st.error("No route is available in the demonstration network for this origin and destination.")

with tab4:
    st.subheader("Simulated IoT cargo and delivery monitoring")
    st.write("Generate a simulated trip record with cargo-condition readings, sensor health and delivery progress. No physical sensor is connected.")
    route_summary = st.session_state.get("route_summary")
    vehicle_type = st.session_state.get("route_vehicle_type", st.session_state.get("selected_vehicle", "Refrigerated truck"))
    trip_hours = route_summary["hours"] if route_summary else 8.0
    st.caption(f"Monitoring scenario: {origin} to {destination} | estimated trip duration: {trip_hours:.1f} hours | vehicle: {vehicle_type}")
    if st.button("Generate / refresh simulated IoT trip", type="primary"):
        st.session_state["iot_seed"] = st.session_state.get("iot_seed", 12) + 1
        st.session_state["iot_generated"] = True
    if "iot_seed" not in st.session_state:
        st.session_state["iot_seed"] = 12
    readings = simulate_iot(
        trip_hours, target_min, target_max, vehicle_type,
        humidity_min, humidity_max, oxygen_min, oxygen_max,
        st.session_state["iot_seed"]
    )
    st.markdown("**Cargo-condition trends**")
    chart1, chart2, chart3 = st.columns(3)
    with chart1:
        st.caption("Temperature (°C)")
        st.line_chart(readings.set_index("Trip hour")[["Simulated temperature (°C)"]])
    with chart2:
        st.caption("Relative humidity (%)")
        st.line_chart(readings.set_index("Trip hour")[["Simulated relative humidity (%)"]])
    with chart3:
        st.caption("Oxygen (%)")
        st.line_chart(readings.set_index("Trip hour")[["Simulated oxygen (%)"]])

    temp_alerts = int(readings["Temperature alert"].sum())
    humidity_alerts = int(readings["Humidity alert"].sum())
    oxygen_alerts = int(readings["Oxygen alert"].sum())
    connection_alerts = int((readings["Sensor status"] != "Online").sum())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Simulated readings", len(readings))
    m2.metric("Temperature alerts", temp_alerts)
    m3.metric("Humidity alerts", humidity_alerts)
    m4.metric("Oxygen alerts", oxygen_alerts)
    if temp_alerts or humidity_alerts or oxygen_alerts or connection_alerts:
        st.warning(
            f"Simulation generated {temp_alerts + humidity_alerts + oxygen_alerts} cargo-condition alert(s) "
            f"and {connection_alerts} sensor-connection warning(s). Review the table below."
        )
    else:
        st.success("No simulated condition or sensor-connection alerts were generated in this run.")

    elapsed_fraction = min(1.0, max(0.0, (len(readings) - 1) / max(1.0, trip_hours)))
    progress = int(elapsed_fraction * 100)
    st.markdown("**Delivery progress (simulation)**")
    st.progress(progress, text=f"Simulated trip timeline: {progress}%")
    st.caption("This progress bar represents the generated trip timeline, not live vehicle location or confirmed delivery status.")

    st.markdown("**Sensor health and reading log**")
    st.dataframe(readings, use_container_width=True, hide_index=True)
    report = readings.copy()
    report.insert(0, "Commodity", commodity)
    report.insert(1, "Origin", origin)
    report.insert(2, "Destination", destination)
    report.insert(3, "Vehicle type", vehicle_type)
    report.insert(4, "Estimated trip hours", round(trip_hours, 2))
    st.download_button("Download full IoT monitoring report (CSV)", report.to_csv(index=False), "agri_logistics_iot_report.csv", "text/csv")

st.divider()
st.caption(
    "Project boundary: 20 demonstration commodity profiles, rule-based vehicle recommendation, route optimization across selected Nigerian corridors, "
    "and simulated multi-parameter IoT monitoring. Replace demonstration assumptions with verified operational data before real-world use."
)
