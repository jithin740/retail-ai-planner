import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from spatial_engine import get_drive_time_buffer, fetch_competitors, calculate_market_scores
from ai_agent import generate_spatial_report

st.set_page_config(layout="wide", page_title="AI Market Planner Agent")

st.title("📍 Advanced AI Retail Market Planner")
st.caption("Live Isochrone Network Mapping & Competitor POI Visualization Engine")

col1, col2 = st.columns([1, 1])

# Initialize session state variables so data doesn't vanish on rerun
if "map_center" not in st.session_state:
    st.session_state.map_center = [12.9716, 77.5946] # Bangalore default
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if "spatial_results" not in st.session_state:
    st.session_state.spatial_results = {}

with col1:
    st.header("1. Input Parameters")
    target_brand = st.text_input("Enter Your Expansion Brand Name:", value="KFC")

# Listen for map click inputs on the base map only if we aren't displaying results yet
if not st.session_state.analysis_done:
    with col1:
        m = folium.Map(location=st.session_state.map_center, zoom_start=14)
        m.add_child(folium.LatLngPopup())
        map_data = st_folium(m, height=400, width=600, key="initial_market_map")

    if map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lon = map_data["last_clicked"]["lng"]
        st.session_state.map_center = [lat, lon]
        
        with st.spinner("Analyzing spatial patterns and transit infrastructure..."):
            # Fetch calculations
            poly, boundary_coords = get_drive_time_buffer(lat, lon)
            gdf, top_10, total_comp, poi_list = fetch_competitors(poly)
            suitability, cannibalization = calculate_market_scores(total_comp, target_brand, top_10)
            
            # Save EVERYTHING to session state so it survives the rerun
            st.session_state.spatial_results = {
                "lat": lat,
                "lon": lon,
                "boundary_coords": boundary_coords,
                "poi_list": poi_list,
                "total_comp": total_comp,
                "suitability": suitability,
                "cannibalization": cannibalization,
                "top_10": top_10
            }
            st.session_state.analysis_done = True
            st.rerun()

# If analysis is done, lock the computed layers onto the screen
if st.session_state.analysis_done:
    res = st.session_state.spatial_results
    
    # Re-build final map with the persistent visual layers
    m_fixed = folium.Map(location=[res["lat"], res["lon"]], zoom_start=14)
    
    # Mark proposed location
    folium.Marker([res["lat"], res["lon"]], tooltip="Proposed Location", icon=folium.Icon(color="red", icon="star")).add_to(m_fixed)
    
    # Draw drive-time polygon boundary
    if res["boundary_coords"]:
        folium.Polygon(
            locations=res["boundary_coords"],
            color="#3186cc",
            weight=3,
            fill=True,
            fill_color="#3186cc",
            fill_opacity=0.2,
            tooltip="1 km True Drive-Time Isochrone"
        ).add_to(m_fixed)
        
    # Plot competitor POI markers
    for poi in res["poi_list"]:
        folium.CircleMarker(
            location=[poi["lat"], poi["lon"]],
            radius=6,
            popup=poi["name"],
            color="orange",
            fill=True,
            fill_color="orange",
            fill_opacity=0.7
        ).add_to(m_fixed)
        
    with col1:
        st.success(f"Calculated Trade Area: {round(res['lat'], 4)}, {round(res['lon'], 4)}")
        
        # Display the static map wrapper that won't flash or clear out
        st_folium(m_fixed, height=400, width=600, key="static_display_map")
        
        # Reset button to clear state and look at another market site selection
        if st.button("Reset & Choose New Location"):
            st.session_state.analysis_done = False
            st.session_state.spatial_results = {}
            st.rerun()
            
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Nearby POIs", res["total_comp"])
        kpi2.metric("Suitability Index", f"{res['suitability']}/100")
        kpi3.metric("Cannibalization Risk", f"{res['cannibalization']}/100")
        
        if res["top_10"]:
            st.subheader("Top 10 Nearby Brands")
            st.dataframe(pd.DataFrame(res["top_10"].items(), columns=["Brand", "Count"]))
            
    with col2:
        st.header("2. Real-Time Generative Site Report")
        try:
            api_key = st.secrets["GROQ_API_KEY"]
            ai_report = generate_spatial_report(target_brand, res["total_comp"], res["top_10"], res["suitability"], res["cannibalization"], api_key)
            st.markdown("---")
            st.markdown(ai_report)
        except Exception:
            st.info("📊 Spatial visualization layers calculated. Hook up an active API key to unlock the textual summary report loop later.")
else:
    with col2:
        st.info("👈 Click anywhere on the map to display the true drive-time network boundary polygon and overlay local commercial storefront nodes.")
