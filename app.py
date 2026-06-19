import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from spatial_engine import get_drive_time_buffer, fetch_competitors, calculate_market_scores
from ai_agent import generate_spatial_report

st.set_page_config(layout="wide", page_title="AI Market Planner Agent")

st.title("📍 Open-Source AI Retail Market Planner & Site Selector")
st.caption("Perfect for live interview demonstrations. Uses OpenStreetMap data and true 1km road network mechanics.")

# Divide the screen into two clean visual columns
col1, col2 = st.columns([1, 1])

with col1:
    st.header("1. Input Parameters")
    target_brand = st.text_input("Enter Your Expansion Brand Name:", value="KFC")
    
    st.subheader("Click on the map to place your proposed storefront:")
    
    # Initialize interactive map focused on a default urban center (Bangalore example)
    default_lat, default_lon = 12.9716, 77.5946 
    m = folium.Map(location=[default_lat, default_lon], zoom_start=14)
    m.add_child(folium.LatLngPopup())
    
    map_data = st_folium(m, height=400, width=600)

# Process spatial calculations immediately when the user clicks the map
if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]
    
    with st.spinner("Calculating 1km Drive-Time Isochrone & querying OSM features..."):
        # 1. Calculate Drive Polygon
        poly = get_drive_time_buffer(lat, lon)
        
        # 2. Extract Open Source Competitor Features
        gdf, top_10, total_comp = fetch_competitors(poly)
        
        # 3. Calculate internal brand counts for Cannibalization evaluation
        internal_count = top_10.get(target_brand, 0)
        suitability, cannibalization = calculate_market_scores(total_comp, internal_count)
        
    with col1:
        st.success(f"Selected Coordinates: {round(lat, 4)}, {round(lon, 4)}")
        
        # Quick KPI Display widgets
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Total Competitors", total_comp)
        kpi2.metric("Suitability Index", f"{suitability}/100")
        kpi3.metric("Cannibalization Risk", f"{cannibalization}/100")
        
        # Show Top Brands Table
        if top_10:
            st.subheader("Top 10 Nearby Brands")
            st.dataframe(pd.DataFrame(top_10.items(), columns=["Brand", "Count"]))
            
    with col2:
        st.header("2. Real-Time Generative Site Report")
        with st.spinner("AI Agent synthesizing GIS datasets..."):
            try:
                ai_report = generate_spatial_report(target_brand, total_comp, top_10, suitability, cannibalization)
                st.markdown("---")
                st.markdown(ai_report)
            except Exception as e:
                st.error("Please ensure your LLM API Environment Variable is configured to render the live report.")
                st.info("Spatial data calculated successfully! Hook up an LLM API key to unlock the automatic corporate reporting module.")
else:
    with col2:
        st.info("👈 Click anywhere on the map to trigger the spatial analytics loop and generate the AI Agent analysis.")