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
