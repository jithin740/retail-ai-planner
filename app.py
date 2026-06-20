import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from spatial_engine import get_drive_time_buffer, fetch_competitors, calculate_market_scores
from geocoder_engine import geocode_location
from report_engine import generate_ai_report_direct
from grid_engine import generate_h3_grid, rank_h3_grids

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
    
    search_query = st.text_input("🔍 Search Location / City (e.g., 'Indiranagar, Bangalore'):")
    if search_query:
        with st.spinner("Geocoding target coordinates..."):
            found_coords = geocode_location(search_query)
            if found_coords and found_coords != st.session_state.map_center:
                st.session_state.map_center = found_coords
                st.session_state.analysis_done = False
                st.rerun()

def get_category_color(category_str):
    cat = category_str.lower()
    if 'fast food' in cat or 'restaurant' in cat:
        return '#E74C3C'  # Red
    elif 'cafe' in cat:
        return '#E67E22'  # Orange
    elif 'supermarket' in cat or 'mall' in cat:
        return '#2ECC71'  # Green
    return '#9B59B6'      # Purple for general retail

# Dynamic function to compute percentile color ramp symbology
def get_ramp_color(percentile_val):
    if percentile_val >= 0.90:
        return "#1E8449"  # Top 10% - Deep Dark Green (Hotspot)
    elif percentile_val >= 0.70:
        return "#2ECC71"  # Top 10% - 30% - Light Vibrant Green
    elif percentile_val >= 0.50:
        return "#F4D03F"  # Top 30% - 50% - Warm Yellow
    elif percentile_val >= 0.25:
        return "#DC7633"  # Top 50% - 75% - Muted Orange
    return "#E74C3C"      # Bottom 25% - Red (Saturated / Unfavorable)

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
                "poly": poly,
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
        tooltip_html = f"<b>Asset:</b> {poi['name']}<br><b>Category:</b> {poi['category']}"
        
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
            if "ranked_grids" in st.session_state.spatial_results:
                del st.session_state.spatial_results["ranked_grids"]
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
            ai_report = generate_ai_report_direct(target_brand, res["total_comp"], res["top_10"], res["suitability"], res["cannibalization"], api_key)
            st.markdown("---")
            st.markdown(ai_report)
        except Exception as e:
            st.info("📊 Spatial infrastructure layer compiled successfully.")

        st.markdown("---")
        st.header("3. Multi-Criteria Hexagonal Optimization")
        
        if not res["df_clean"].empty:
            unique_categories = sorted(res["df_clean"]["Category"].unique())
            
            st.subheader("💡 Set Category Evaluation Weights")
            st.caption("Assign relative prioritization weights to local categories. Total sum must equal exactly 100%.")
            
            category_weights = {}
            total_allocated_weight = 0
            
            for cat in unique_categories:
                val = st.number_input(f"Weight (%) for {cat}:", min_value=0, max_value=100, value=0, step=5, key=f"weight_{cat}")
                category_weights[cat] = val
                total_allocated_weight += val
                
            if total_allocated_weight == 100:
                st.success(f"✅ Total Weight Configuration: {total_allocated_weight}% / 100% (Balanced)")
                
                st.subheader("📐 Uber H3 Grid Settings")
                # Dynamic picker mapped directly to standardized Uber H3 granularity scales
                h3_res_choice = st.select_slider(
                    "Select Uber H3 Granularity (Resolution Level):", 
                    options=[8, 9, 10], 
                    value=9,
                    format_func=lambda x: f"Res {x} (~170m cells)" if x==9 else (f"Res {x} (~460m cells)" if x==8 else f"Res {x} (~65m cells)")
                )
                
                if st.button("🚀 Calculate Hexagonal Grid Rankings"):
                    with st.spinner("Computing H3 spatial tiles and mapping score ranks..."):
                        h3_cells = generate_h3_grid(res["poly"], h3_res_choice)
                        ranked_grids = rank_h3_grids(h3_cells, res["poi_list"], category_weights)
                        
                        if ranked_grids:
                            st.session_state.spatial_results["ranked_grids"] = ranked_grids
                            st.success("H3 Multi-Criteria Matrix calculated completely!")
            else:
                st.warning(f"⚠️ Current Weight Allocation: **{total_allocated_weight}%**. Please adjust category inputs to total exactly 100% to unlock optimization.")
                
            if "ranked_grids" in res:
                st.subheader("🗺️ Micro-Market Optimization Heatmap")
                st.caption("Color Ramp Symbology: Green = Top Hotspots, Red = Saturated Tiers.")
                
                m_hex = folium.Map(location=[res["lat"], res["lon"]], zoom_start=15)
                
                # DRAW TRADE AREA OVERLAY BOUNDARY AGAIN ON TOP OF THE HEX MAP
                if res["boundary_coords"]:
                    folium.Polygon(
                        locations=res["boundary_coords"],
                        color="#2E4053",
                        weight=4,
                        fill=False,
                        tooltip="1 km Core Isochrone Boundary Reference"
                    ).add_to(m_hex)
                
                folium.Marker([res["lat"], res["lon"]], tooltip="Proposed Location Site", icon=folium.Icon(color="black", icon="star")).add_to(m_hex)
                
                max_rank = len(res["ranked_grids"])
                
                for g in res["ranked_grids"]:
                    # Fetch color dynamic ramp based on performance percentile distributions
                    fill_color = get_ramp_color(g["percentile"])
                    
                    popup_hover_text = f"""
                    <div style='font-family:Arial, sans-serif; font-size:12px; line-height:1.4; padding:5px;'>
                        <b>H3 Cell Rank:</b> #{g['rank']} of {max_rank}<br>
                        <b>Suitability Score:</b> {round(g['score']*100, 1)} pts<br>
                        <b>Total Retail Nodes Inside:</b> {g['total_density']} stores
                    </div>
                    """
                    
                    # Render H3 cells using the dynamic color ramp symbology
                    folium.Polygon(
                        locations=g["boundary_locations"],
                        color="#7F8C8D",
                        weight=1.5,
                        fill=True,
                        fill_color=fill_color,
                        fill_opacity=0.45,
                        tooltip=folium.Tooltip(popup_hover_text)
                    ).add_to(m_hex)
                    
                    # ADD TEXT LABELS DIRECTLY ON TOP OF EACH HEXAGON CELL DISPLAYING THE EXPLICIT RANK
                    label_html = f"""
                    <div style="font-family: 'Arial Black', sans-serif; font-size: 11px; 
                                color: #2C3E50; font-weight: bold; width: 24px; height: 24px; 
                                text-align: center; line-height: 24px; 
                                background-color: rgba(255,255,255,0.75); 
                                border: 1px solid #BDC3C7; border-radius: 50%;">
                        {g['rank']}
                    </div>
                    """
                    folium.Marker(
                        location=[g["centroid_lat"], g["centroid_lon"]],
                        icon=folium.features.DivIcon(
                            html=label_html,
                            icon_size=(24, 24),
                            icon_anchor=(12, 12)
                        )
                    ).add_to(m_hex)
                    
                st_folium(m_hex, height=450, width=600, key="hexagonal_grid_optimizer_map")
else:
    with col2:
        st.info("👈 Click anywhere on the map grid to display the true drive-time network boundary polygon and overlay local commercial storefront nodes.")
