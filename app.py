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

if "map_center" not in st.session_state:
    st.session_state.map_center = [12.9716, 77.5946] # Bangalore Default
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if "spatial_results" not in st.session_state:
    st.session_state.spatial_results = {}

with col1:
    st.header("1. Input Parameters")
    target_brand = st.text_input("Enter Your Expansion Brand Name:", value="KFC")

def get_category_color(category_str):
    cat = category_str.lower()
    if 'fast food' in cat or 'restaurant' in cat:
        return '#E74C3C'  # Red
    elif 'cafe' in cat:
        return '#E67E22'  # Orange
    elif 'supermarket' in cat or 'mall' in cat:
        return '#2ECC71'  # Green
    return '#9B59B6'      # Purple for general retail

if not st.session_state.analysis_done:
    with col1:
        st.info("💡 Click anywhere on the map grid below to analyze the true 1 km drive-time network.")
        m = folium.Map(location=st.session_state.map_center, zoom_start=14)
        m.add_child(folium.LatLngPopup())
        map_data = st_folium(m, height=400, width=600, key="initial_market_map")

    if map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lon = map_data["last_clicked"]["lng"]
        st.session_state.map_center = [lat, lon]
        
        with st.spinner("Processing network elements..."):
            poly, boundary_coords = get_drive_time_buffer(lat, lon)
            df_clean, top_10, total_comp, poi_list = fetch_competitors(lat, lon, poly)
            suitability, cannibalization = calculate_market_scores(total_comp, target_brand, top_10)
            
            st.session_state.spatial_results = {
                "lat": lat,
                "lon": lon,
                "boundary_coords": boundary_coords,
                "poi_list": poi_list,
                "total_comp": total_comp,
                "suitability": suitability,
                "cannibalization": cannibalization,
                "top_10": top_10,
                "df_clean": df_clean
            }
            st.session_state.analysis_done = True
            st.rerun()

if st.session_state.analysis_done:
    res = st.session_state.spatial_results
    m_fixed = folium.Map(location=[res["lat"], res["lon"]], zoom_start=15)
    
    folium.Marker([res["lat"], res["lon"]], tooltip="Target Store Site", icon=folium.Icon(color="black", icon="star")).add_to(m_fixed)
    
    if res["boundary_coords"]:
        folium.Polygon(
            locations=res["boundary_coords"],
            color="#2980B9",
            weight=3,
            fill=True,
            fill_color="#3498DB",
            fill_opacity=0.15,
            tooltip="1 km Drive Buffer Boundaries"
        ).add_to(m_fixed)
        
    for poi in res["poi_list"]:
        color = get_category_color(poi["category"])
        
        tooltip_html = f"""
        <div style="font-family: Arial, sans-serif; font-size: 12px; padding: 4px; line-height:1.4;">
            <strong>Asset:</strong> {poi['name']}<br>
            <strong>Category:</strong> {poi['category']}<br>
            <strong>Position:</strong> {round(poi['lat'],4)}, {round(poi['lon'],4)}
        </div>
        """
        
        folium.Circle(
            location=[poi["lat"], poi["lon"]],
            radius=16,
            tooltip=folium.Tooltip(tooltip_html),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8
        ).add_to(m_fixed)
        
    with col1:
        st.success(f"Calculated Target Site Location: {round(res['lat'], 4)}, {round(res['lon'], 4)}")
        st_folium(m_fixed, height=400, width=600, key="static_display_map")
        
        if st.button("🔄 Reset & Choose New Location"):
            st.session_state.analysis_done = False
            st.session_state.spatial_results = {}
            st.rerun()
            
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Unique Retail POIs", res["total_comp"])
        kpi2.metric("Suitability Index", f"{res['suitability']}/100")
        kpi3.metric("Cannibalization Risk", f"{res['cannibalization']}/100")
        
        if not res["df_clean"].empty:
            st.subheader("📋 Complete Asset Location Matrix")
            st.dataframe(res["df_clean"], use_container_width=True, height=200)
            
    with col2:
        st.header("2. Real-Time Generative Site Report")
        try:
            api_key = st.secrets["GROQ_API_KEY"]
            ai_report = generate_spatial_report(target_brand, res["total_comp"], res["top_10"], res["suitability"], res["cannibalization"], api_key)
            st.markdown("---")
            st.markdown(ai_report)
        except Exception:
            st.info("📊 Spatial infrastructure layer compiled successfully. Insert an active API key to unlock the text report summarizer module.")
else:
    with col2:
        st.info("👈 Click anywhere on the map grid to display the true drive-time network boundary polygon and overlay local commercial storefront nodes.")
