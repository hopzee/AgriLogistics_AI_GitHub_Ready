# AgriLogistics AI — GitHub-ready Streamlit prototype

**Project:** AI-Driven Vehicle Recommendation and Route Optimization System for Perishable Agricultural Commodities.

## Scope implemented

- Vehicle recommendation using cargo payload, refrigeration temperature range, availability, maintenance score, maintenance-event history and last service date.
- User interface for agricultural cooperative managers, logistics operators and drivers.
- Route comparison between a distance-only route and a weighted perishability-aware route.
- Route cost includes distance, estimated travel time and a simplified temperature-exposure proxy.
- Simulated IoT temperature readings, without physical sensors.
- CSV upload/download for fleet and route outputs.

## Important limitations

All fleet records, commodity temperature ranges, route distances, road/traffic assumptions and IoT readings included here are illustrative. The temperature-exposure proxy is not a validated biological spoilage model. The application has no live GPS, live traffic feed, external map routing API or verified fleet telemetry. It must not be used as a real dispatch or food-safety system without replacing demonstration assumptions with validated data.

The route graph is a small demonstration network for Nigerian corridors. It does not represent all roads or current road conditions. Route evaluation compares algorithms under the same illustrative graph; it does not prove real-world reductions in spoilage or cost.

## Run locally

Python 3.10 or newer is recommended.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub and Streamlit Community Cloud

1. Extract the ZIP file.
2. Upload the contents of this folder to a GitHub repository.
3. Create a Streamlit Community Cloud app from that repository.
4. Set `app.py` as the main file.

No Supabase, database, API key, or separate backend is required for this prototype.

## Fleet CSV columns

`vehicle_id, vehicle_type, capacity_kg, refrigeration_type, min_temp_c, max_temp_c, maintenance_score, maintenance_events_12m, last_service_date, available`

Use actual fleet records and verified temperature-handling requirements before interpreting recommendations operationally.
