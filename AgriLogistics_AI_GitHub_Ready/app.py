import heapq
from datetime import datetime, timedelta
import random

import pandas as pd
import streamlit as st

st.set_page_config(page_title="AgriLogistics AI", page_icon="🚚", layout="wide")

# Demonstration corridor network only. Distances, road conditions and traffic
# factors are illustrative and must be replaced with verified route data.
NODES = {
    "Kano": (12.0022, 8.5920), "Kaduna": (10.5105, 7.4165),
    "Zaria": (11.0855, 7.7199), "Jos": (9.8965, 8.8583),
    "Abuja": (9.0765, 7.3986), "Lokoja": (7.8023, 6.7430),
    "Ilorin": (8.4966, 4.5421), "Ibadan": (7.3775, 3.9470),
    "Lagos": (6.5244, 3.3792), "Benin City": (6.3350, 5.6037),
    "Onitsha": (6.1667, 6.7833), "Port Harcourt": (4.8156, 7.0498),
}
EDGES = [
    ("Kano","Kaduna",190,2.8,"Fair","Medium"),
    ("Kano","Zaria",75,1.2,"Fair","Low"),
    ("Zaria","Kaduna",75,1.2,"Good","Medium"),
    ("Kaduna","Abuja",185,2.8,"Fair","Medium"),
    ("Kaduna","Jos",220,3.8,"Fair","Low"),
    ("Jos","Abuja",280,4.4,"Fair","Medium"),
    ("Abuja","Lokoja",190,3.0,"Fair","Medium"),
    ("Lokoja","Ilorin",220,3.6,"Fair","Low"),
    ("Ilorin","Ibadan",160,2.5,"Good","Medium"),
    ("Ibadan","Lagos",130,2.3,"Good","High"),
    ("Lokoja","Benin City",210,3.6,"Fair","Medium"),
    ("Benin City","Ibadan",250,4.0,"Fair","Medium"),
    ("Benin City","Onitsha",115,2.0,"Fair","High"),
    ("Onitsha","Port Harcourt",150,2.7,"Fair","Medium"),
    ("Lagos","Benin City",300,4.8,"Fair","High"),
]
ROAD_FACTOR={"Good":1.0,"Fair":1.18,"Poor":1.45}
TRAFFIC_FACTOR={"Low":1.0,"Medium":1.18,"High":1.45}

DEFAULT_FLEET = pd.DataFrame([
    {"vehicle_id":"REF-001","vehicle_type":"Refrigerated truck","capacity_kg":8000,"refrigeration_type":"Chilled","min_temp_c":8,"max_temp_c":15,"maintenance_score":92,"maintenance_events_12m":1,"last_service_date":"2026-08-10","available":True},
    {"vehicle_id":"REF-002","vehicle_type":"Refrigerated van","capacity_kg":2500,"refrigeration_type":"Chilled","min_temp_c":7,"max_temp_c":14,"maintenance_score":88,"maintenance_events_12m":2,"last_service_date":"2026-07-22","available":True},
    {"vehicle_id":"FRO-003","vehicle_type":"Refrigerated truck","capacity_kg":10000,"refrigeration_type":"Frozen","min_temp_c":-18,"max_temp_c":-5,"maintenance_score":90,"maintenance_events_12m":1,"last_service_date":"2026-09-01","available":True},
    {"vehicle_id":"INS-004","vehicle_type":"Insulated truck","capacity_kg":5000,"refrigeration_type":"Insulated","min_temp_c":10,"max_temp_c":25,"maintenance_score":82,"maintenance_events_12m":3,"last_service_date":"2026-05-18","available":True},
    {"vehicle_id":"OPEN-005","vehicle_type":"Open truck","capacity_kg":6000,"refrigeration_type":"None","min_temp_c":20,"max_temp_c":40,"maintenance_score":75,"maintenance_events_12m":4,"last_service_date":"2026-04-12","available":True},
    {"vehicle_id":"REF-006","vehicle_type":"Refrigerated van","capacity_kg":1800,"refrigeration_type":"Chilled","min_temp_c":7,"max_temp_c":14,"maintenance_score":65,"maintenance_events_12m":5,"last_service_date":"2026-02-11","available":False},
])
COMMODITIES = {
    "Tomatoes": (10.0,15.0,1.25),
    "Pepper": (7.0,12.0,1.15),
    "Citrus fruits": (4.0,10.0,0.85),
}

def validate_fleet(df):
    required={"vehicle_id","vehicle_type","capacity_kg","refrigeration_type","min_temp_c","max_temp_c","maintenance_score","maintenance_events_12m","last_service_date","available"}
    missing=required-set(df.columns)
    if missing:
        raise ValueError("Fleet file is missing columns: "+", ".join(sorted(missing)))
    out=df.copy()
    for c in ["capacity_kg","min_temp_c","max_temp_c","maintenance_score","maintenance_events_12m"]:
        out[c]=pd.to_numeric(out[c],errors="coerce")
    if out[list(["capacity_kg","min_temp_c","max_temp_c","maintenance_score","maintenance_events_12m"])].isna().any().any():
        raise ValueError("Fleet numeric fields contain blank or invalid values.")
    if (out.capacity_kg<=0).any() or ((out.min_temp_c>out.max_temp_c).any()):
        raise ValueError("Check that capacities are positive and minimum temperatures do not exceed maximum temperatures.")
    out["available"]=out["available"].astype(str).str.lower().isin(["true","1","yes","available"])
    out["last_service_date"]=pd.to_datetime(out["last_service_date"],errors="coerce")
    return out

def vehicle_ranking(fleet, load_kg, target_min, target_max):
    rows=[]
    span=max(0.1,target_max-target_min)
    for _,v in fleet.iterrows():
        overlap=max(0.0,min(v.max_temp_c,target_max)-max(v.min_temp_c,target_min))
        temp_match=min(1.0,overlap/span)
        capacity_match=min(1.0,v.capacity_kg/max(load_kg,1))
        service_score=max(0.0,min(100.0,float(v.maintenance_score)))
        history_penalty=min(20.0,float(v.maintenance_events_12m)*2.0)
        score=100*(0.50*temp_match+0.20*min(1.0,capacity_match)+0.30*(service_score/100))-history_penalty
        reasons=[]
        if not bool(v.available): reasons.append("Vehicle unavailable")
        if v.capacity_kg<load_kg: reasons.append("Insufficient payload capacity")
        if temp_match<0.35: reasons.append("Refrigeration range does not sufficiently match cargo requirement")
        eligible=not reasons
        rows.append({"Vehicle ID":v.vehicle_id,"Vehicle type":v.vehicle_type,
                     "Capacity (kg)":int(v.capacity_kg),"Refrigeration":v.refrigeration_type,
                     "Temperature range (°C)":f"{v.min_temp_c:g} to {v.max_temp_c:g}",
                     "Maintenance score":round(service_score,1),
                     "Maintenance events (12 months)":int(v.maintenance_events_12m),
                     "Last service":v.last_service_date.strftime("%Y-%m-%d") if pd.notna(v.last_service_date) else "Not recorded",
                     "Available":bool(v.available),"Temperature match (%)":round(temp_match*100,1),
                     "Match score":round(max(0,score),1),"Eligible":eligible,
                     "Decision": "Suitable" if eligible else "; ".join(reasons)})
    return pd.DataFrame(rows).sort_values(["Eligible","Match score"],ascending=[False,False])

def edge_time(edge):
    _,_,km,base_h,road,traffic=edge
    return base_h*ROAD_FACTOR[road]*TRAFFIC_FACTOR[traffic]

def find_route(start,goal,target_min,target_max,ambient_temp,vehicle_type,weights):
    graph={n:[] for n in NODES}
    info={}
    for e in EDGES:
        a,b,km,base_h,road,traffic=e
        hours=edge_time(e)
        # This is a transparent exposure proxy, not a biological spoilage model.
        deviation=max(0,target_min-ambient_temp,ambient_temp-target_max)
        vehicle_buffer={"Refrigerated truck":0.25,"Refrigerated van":0.30,
                        "Insulated truck":0.55,"Open truck":1.0}.get(vehicle_type,0.7)
        exposure=hours*deviation*vehicle_buffer
        info[(a,b)]={"km":km,"hours":hours,"road":road,"traffic":traffic,"exposure":exposure}
        info[(b,a)]=info[(a,b)]
        # Normalize distance/time/exposure into a weighted routing cost.
        cost=weights[0]*(km/100)+weights[1]*hours+weights[2]*exposure
        graph[a].append((b,cost)); graph[b].append((a,cost))
    def dijkstra(distance_only=False):
        q=[(0,start,[start])]; best={start:0}
        while q:
            cost,node,path=heapq.heappop(q)
            if node==goal:
                legs=[info[(path[i],path[i+1])] for i in range(len(path)-1)]
                return path,legs
            if cost>best.get(node,float("inf")): continue
            for nxt,_ in graph[node]:
                leg=info[(node,nxt)]
                w=leg["km"] if distance_only else weights[0]*(leg["km"]/100)+weights[1]*leg["hours"]+weights[2]*leg["exposure"]
                nc=cost+w
                if nc<best.get(nxt,float("inf")):
                    best[nxt]=nc; heapq.heappush(q,(nc,nxt,path+[nxt]))
        return [],[]
    return dijkstra(True),dijkstra(False)

def summarize(path,legs):
    return {"path":path,"distance_km":sum(x["km"] for x in legs),
            "hours":sum(x["hours"] for x in legs),
            "exposure_proxy":sum(x["exposure"] for x in legs),
            "legs":legs}

def simulate_temperature(hours,target_min,target_max,vehicle_type,seed=12):
    rng=random.Random(seed)
    mid=(target_min+target_max)/2
    buffer={"Refrigerated truck":0.5,"Refrigerated van":0.8,
            "Insulated truck":1.8,"Open truck":4.0}.get(vehicle_type,2.5)
    n=max(2,min(72,int(hours)+1))
    now=datetime.now()
    vals=[]
    for i in range(n):
        val=mid+rng.uniform(-buffer,buffer)
        vals.append({"Hour":i,"Simulated cargo temperature (°C)":round(val,1),
                     "Timestamp":now+timedelta(hours=i)})
    return pd.DataFrame(vals)

st.title("🚚 AgriLogistics AI")
st.caption("Vehicle recommendation and route optimization for perishable agricultural commodities in Nigerian trade corridors")
st.info("Prototype notice: route distances, traffic, road conditions, fleet records, commodity temperature ranges and temperature readings are illustrative assumptions. This application does not provide live GPS, live traffic, verified spoilage estimates or dispatch instructions.")

with st.sidebar:
    st.header("Shipment details")
    commodity=st.selectbox("Commodity",list(COMMODITIES))
    default_min,default_max,sensitivity=COMMODITIES[commodity]
    target_min=st.number_input("Required cargo temperature minimum (°C)",value=float(default_min),step=0.5)
    target_max=st.number_input("Required cargo temperature maximum (°C)",value=float(default_max),step=0.5)
    if target_min>=target_max: st.error("Maximum temperature must be greater than minimum temperature.")
    load=st.number_input("Cargo weight (kg)",min_value=1,max_value=30000,value=2000,step=100)
    origin=st.selectbox("Origin",list(NODES),index=list(NODES).index("Kano"))
    dests=[n for n in NODES if n!=origin]
    destination=st.selectbox("Destination",dests,index=dests.index("Lagos") if "Lagos" in dests else 0)
    ambient=st.number_input("Assumed average ambient temperature (°C)",value=30.0,step=0.5)
    st.caption("Edit temperature requirements using verified commodity-handling guidance before operational use.")

tab1,tab2,tab3,tab4=st.tabs(["Overview","Vehicle recommendation","Route comparison","Simulated IoT monitoring"])
with tab1:
    st.subheader("Shipment planning")
    c1,c2,c3=st.columns(3)
    c1.metric("Commodity",commodity); c2.metric("Cargo weight",f"{load:,.0f} kg")
    c3.metric("Cargo temperature range",f"{target_min:g}–{target_max:g} °C")
    st.write("The prototype combines vehicle suitability screening, route comparison and simulated cargo-temperature monitoring.")
    st.markdown("**Workflow**")
    st.markdown(
    "1. Enter the cargo and shipment details. "
    "2. Review eligible vehicles using payload, refrigeration and maintenance information. "
    "3. Compare the distance-only route with the perishability-aware route. "
    "4. Inspect simulated temperature readings."
)
    
with tab2:
    st.subheader("Vehicle recommendation engine")
    uploaded=st.file_uploader("Optional: upload your fleet CSV",type=["csv"],key="fleet_csv")
    try:
        fleet=validate_fleet(pd.read_csv(uploaded) if uploaded else DEFAULT_FLEET)
        ranked=vehicle_ranking(fleet,load,target_min,target_max)
        eligible=ranked[ranked["Eligible"]]
        if len(eligible):
            best=eligible.iloc[0]
            st.success(f"Top eligible vehicle: {best['Vehicle ID']} — {best['Vehicle type']} (match score {best['Match score']}/100)")
            st.session_state["selected_vehicle"]=best["Vehicle type"]
        else:
            st.error("No vehicle currently satisfies all selected constraints. Review the cargo requirements, load weight or fleet records.")
        st.dataframe(ranked,use_container_width=True,hide_index=True)
        st.caption("The score is a transparent rule-based ranking, not a trained AI prediction. Maintenance score, service-event count and last service date are displayed; the score and event count influence ranking.")
        st.download_button("Download fleet CSV",fleet.to_csv(index=False),"vehicle_fleet.csv","text/csv")
    except Exception as e:
        st.error(f"Fleet data could not be processed: {e}")

with tab3:
    st.subheader("Distance-only versus perishability-aware route")
    w1,w2,w3=st.columns(3)
    wd=w1.slider("Distance importance",0.0,5.0,2.0,0.1)
    wt=w2.slider("Travel-time importance",0.0,5.0,2.0,0.1)
    we=w3.slider("Temperature-exposure importance",0.0,5.0,2.0,0.1)
    selected_type=st.session_state.get("selected_vehicle","Refrigerated truck")
    (base_path,base_legs),(opt_path,opt_legs)=find_route(origin,destination,target_min,target_max,ambient,selected_type,(wd,wt,we))
    if base_path and opt_path:
        base_s=summarize(base_path,base_legs); opt_s=summarize(opt_path,opt_legs)
        st.write(f"**Distance-only route:** {' → '.join(base_path)}")
        st.write(f"**Perishability-aware route:** {' → '.join(opt_path)}")
        rows=[]
        for label,s in [("Distance-only",base_s),("Perishability-aware",opt_s)]:
            rows.append({"Route":label,"Distance (km)":round(s["distance_km"],1),
                         "Estimated hours":round(s["hours"],2),
                         "Temperature-exposure proxy":round(s["exposure_proxy"],2)})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        if base_s["hours"]>0:
            st.metric("Estimated time difference",f"{base_s['hours']-opt_s['hours']:+.2f} hours",
                      help="Positive means the optimized route is faster under the illustrative assumptions.")
        st.caption("The route engine uses Dijkstra's algorithm. The exposure proxy is a simplified temperature-deviation indicator multiplied by estimated trip time and a vehicle-type buffer. It is not a validated estimate of actual product spoilage.")
        st.markdown("**Optimized route segments**")
        legs_df=pd.DataFrame([{"From":opt_path[i],"To":opt_path[i+1],
            "Distance (km)":x["km"],"Estimated hours":round(x["hours"],2),
            "Road condition":x["road"],"Traffic assumption":x["traffic"],
            "Exposure proxy":round(x["exposure"],2)} for i,x in enumerate(opt_legs)])
        st.dataframe(legs_df,use_container_width=True,hide_index=True)
        st.map(pd.DataFrame([{"lat":NODES[n][0],"lon":NODES[n][1]} for n in opt_path]),latitude="lat",longitude="lon")
        st.download_button("Download route comparison CSV",pd.DataFrame(rows).to_csv(index=False),"route_comparison.csv","text/csv")
        st.session_state["route_summary"]=opt_s
        st.session_state["route_vehicle_type"]=selected_type
    else:
        st.error("No route is available in the demonstration network.")

with tab4:
    st.subheader("Simulated IoT temperature stream")
    st.write("This feature represents the project's simulated IoT scope; no physical sensor or live telemetry connection is required.")
    route=st.session_state.get("route_summary")
    vehicle_type=st.session_state.get("route_vehicle_type","Refrigerated truck")
    trip_hours=route["hours"] if route else 8
    if st.button("Generate simulated temperature stream"):
        st.session_state["iot_seed"]=st.session_state.get("iot_seed",12)+1
    temp_df=simulate_temperature(trip_hours,target_min,target_max,vehicle_type,st.session_state.get("iot_seed",12))
    st.line_chart(temp_df.set_index("Hour")[["Simulated cargo temperature (°C)"]])
    outside=temp_df[(temp_df["Simulated cargo temperature (°C)"]<target_min)|
                    (temp_df["Simulated cargo temperature (°C)"]>target_max)]
    a,b=st.columns(2); a.metric("Simulated readings",len(temp_df)); b.metric("Outside selected range",len(outside))
    if len(outside): st.warning("Some simulated readings are outside the user-selected cargo temperature range.")
    else: st.success("All simulated readings are within the selected cargo temperature range.")
    st.download_button("Download simulated IoT readings",temp_df.to_csv(index=False),"simulated_iot_temperature.csv","text/csv")

st.divider()
st.caption("Project boundary: perishable produce, vehicle recommendation, route optimization across selected Nigerian corridors and simulated IoT temperature streams.")
