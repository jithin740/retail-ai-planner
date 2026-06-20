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

with col1:
    st.header("1. Input Parameters")
    target_brand = st.text_input("Enter Your Expansion Brand Name:", value="KFC")
    
    # Track coordinates in session state so the map keeps them across updates
    if "map_center" not in st.session_state:
        st.session_state.map_center = [12.9716, 77.5946] # Bangalore default
        
    m = folium.Map(location=st.session_state.map_center, zoom_start=14)
    m.add_child(folium.LatLngPopup())

# Listen for map click inputs
map_data = st_folium(m, height=400, width=600, key="market_map")

if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]
    st.session_state.map_center = [lat, lon]
    
    with st.spinner("Analyzing spatial patterns and transit infrastructure..."):
        # 1. Fetch the network polygon geometry boundary
        poly, boundary_coords = get_drive_time_buffer(lat, lon)
        
        # 2. Extract specific POIs
        gdf, top_10, total_comp, poi_list = fetch_competitors(poly)
        
        # 3. Compute structural analytics
        suitability, cannibalization = calculate_market_scores(total_comp, target_brand, top_10)
        
    # Re-build map to draw the custom visual layers
    m_updated = folium.Map(location=[lat, lon], zoom_start=14)
    
    # Mark proposed storefront location
    folium.Marker([lat, lon], tooltip="Proposed Location", icon=folium.Icon(color="red", icon="star")).add_to(m_updated)
    
    # DRAW THE TRUE 1KM DRIVE ISOCHRONE BOUNDARY LAYER
    if boundary_coords:
        folium.Polygon(
            locations=boundary_coords,
            color="#3186cc",
            weight=3,
            fill=True,
            fill_color="#3186cc",
            fill_opacity=0.2,
            tooltip="1 km True Drive-Time Isochrone"
        ).add_to(m_updated)
        
    # PLOT EVERY SINGLE COMPETITOR WITHIN THE DRIVE NETWORK BOUNDARY
    for poi in poi_list:
        folium.CircleMarker(
            location=[poi["lat"], poi["lon"]],
            radius=6,
            popup=poi["name"],
            color="orange",
            fill=True,
            fill_color="orange",
            fill_opacity=0.7
        ).add_to(m_updated)
        
    with col1:
        st.success(f"Calculated Trade Area: {round(lat, 4)}, {round(lon, 4)}")
        
        # Render the enhanced visual map interface over the old layout
        st_folium(m_updated, height=400, width=600, key="updated_render_map")
        
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Nearby POIs", total_comp)
        kpi2.metric("Suitability Index", f"{suitability}/100")
        kpi3.metric("Cannibalization Risk", f"{cannibalization}/100")
        
        if top_10:
            st.subheader("Top 10 Nearby Brands")
            st.dataframe(pd.DataFrame(top_10.items(), columns=["Brand", "Count"]))
            
    with col2:
        st.header("2. Real-Time Generative Site Report")
        try:
            api_key = st.secrets["GROQ_API_KEY"]
            ai_report = generate_spatial_report(target_brand, total_comp, top_10, suitability, cannibalization, api_key)
            st.markdown("---")
            st.markdown(ai_report)
        except Exception:
            st.info("📊 Spatial visualization layers calculated. Hook up an active API key to unlock the textual summary report loop later.")
else:
    with col2:
        st.info("👈 Click anywhere on the map to display the true drive-time network boundary polygon and overlay local commercial storefront nodes.")
