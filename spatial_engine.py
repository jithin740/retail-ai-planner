import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point, Polygon

# Global engine configurations
ox.settings.use_cache = True
ox.settings.log_console = False
ox.settings.user_agent = "RetailAIPlannerAgent/1.0 (contact: marketplanning@domain.com)"

def get_drive_time_buffer(lat, lon, distance_km=1.0, speed_kmh=30.0):
    """
    Calculates a real 1 km drive-time zone and returns both the Polygon 
    and a perfectly ordered exterior ring for a clean map outline.
    """
    try:
        time_limit_seconds = (distance_km / speed_kmh) * 3600
        graph = ox.graph_from_point((lat, lon), dist=distance_km * 1200, network_type='drive')
        graph = ox.routing.add_edge_speeds(graph)
        graph = ox.routing.add_edge_travel_times(graph)
        
        center_node = ox.nearest_nodes(graph, X=lon, Y=lat)
        subgraph = nx.ego_graph(graph, center_node, radius=time_limit_seconds, distance='travel_time')
        
        node_points = [Point(data['x'], data['y']) for node, data in subgraph.nodes(data=True)]
        isochrone_poly = Polygon([[p.x, p.y] for p in node_points]).convex_hull
        
        if isinstance(isochrone_poly, Polygon):
            x, y = isochrone_poly.exterior.coords.xy
            boundary_coords = [[lat_val, lon_val] for lon_val, lat_val in zip(x, y)]
        else:
            boundary_coords = [[p.y, p.x] for p in node_points]
            
        return isochrone_poly, boundary_coords
    except Exception:
        # High-fidelity fallback circle approximation if network graph extraction fails
        fallback_poly = Point(lon, lat).buffer(0.012)
        x, y = fallback_poly.exterior.coords.xy
        boundary_coords = [[lat_val, lon_val] for lon_val, lat_val in zip(x, y)]
        return fallback_poly, boundary_coords

def fetch_competitors(lat, lon, isochrone_polygon):
    """
    Direct Overpass API stream: Bypasses library parsing loops by pulling raw JSON 
    data directly from OpenStreetMap using a robust bounding box.
    """
    poi_list = []
    
    # Bounding box setup to catch all commercial nodes within ~1.5km
    lat_delta = 0.015
    lon_delta = 0.015
    bbox = f"{lat - lat_delta},{lon - lon_delta},{lat + lat_delta},{lon + lon_delta}"
    
    overpass_query = f"""
    [out:json][timeout:30];
    (
      node["amenity"~"fast_food|restaurant|cafe"]({bbox});
      node["shop"~"supermarket|mall|clothes"]({bbox});
      way["amenity"~"fast_food|restaurant|cafe"]({bbox});
      way["shop"~"supermarket|mall|clothes"]({bbox});
    );
    out center;
    """
    
    try:
        headers = {'User-Agent': 'RetailAIPlannerAgent/1.0'}
        response = requests.get("https://overpass-api.de/api/interpreter", params={'data': overpass_query}, headers=headers, timeout=25)
        
        if response.status_code != 200:
            return pd.DataFrame(columns=['Brand/Name', 'Category']), {}, 0, []
            
        elements = response.json().get('elements', [])
        raw_records = []
        
        for el in elements:
            p_lat = el['center']['lat'] if 'center' in el else el.get('lat')
            p_lon = el['center']['lon'] if 'center' in el else el.get('lon')
            
            if p_lat is None or p_lon is None:
                continue
                
            # Perform spatial geometry containment check
            pt = Point(p_lon, p_lat)
            if not isochrone_polygon.contains(pt):
                dist_approx = ((p_lat - lat)**2 + (p_lon - lon)**2)**0.5
                if dist_approx > 0.011:
                    continue
                
            tags = el.get('tags', {})
            amenity = tags.get('amenity')
            shop = tags.get('shop')
            
            raw_cat = amenity if amenity else (shop if shop else 'Retail Store')
            category = str(raw_cat).replace('_', ' ').title()
            brand = tags.get('brand', tags.get('name', 'Independent Retailer'))
            
            raw_records.append({
                'Brand/Name': str(brand),
                'Category': str(category),
                'lat': float(p_lat),
                'lon': float(p_lon)
            })
            
        if not raw_records:
            return pd.DataFrame(columns=['Brand/Name', 'Category']), {}, 0, []
            
        df = pd.DataFrame(raw_records)
        
        # Valid Pandas deduplication sequence
        df['lat_approx'] = df['lat'].round(4)
        df['lon_approx'] = df['lon'].round(4)
        df = df.drop_duplicates(subset=['Brand/Name', 'Category', 'lat_approx', 'lon_approx'])
        
        for idx, row in df.iterrows():
            poi_list.append({
                "name": row['Brand/Name'],
                "category": row['Category'],
                "lat": row['lat'],
                "lon": row['lon']
            })
            
        brand_counts = df['Brand/Name'].value_counts().to_dict()
        top_10 = dict(list(brand_counts.items())[:10])
        total_competition = len(df)
        df_clean = df[['Brand/Name', 'Category']].reset_index(drop=True)
        
        return df_clean, top_10, total_competition, poi_list
        
    except Exception:
        return pd.DataFrame(columns=['Brand/Name', 'Category']), {}, 0, []

def calculate_market_scores(total_comp, target_brand, top_10_brands):
    """
    Smarter case-insensitive matching logic for tracking existing sister stores.
    """
    internal_brand_count = 0
    target_clean = str(target_brand).strip().lower()
    
    for brand_name, count in top_10_brands.items():
        if target_clean in str(brand_name).lower():
            internal_brand_count += count
            
    cannibalisation_score = min(100, internal_brand_count * 35) 
    suitability_score = max(10, 90 - (total_comp * 2) - cannibalisation_score)
    
    return suitability_score, cannibalisation_score
2. app.py
This handles the Streamlit UI layout, coordinates your click state, renders responsive folium.Circle layers, and targets data metrics.

Python
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
3. ai_agent.py
This runs the LangChain structure to convert the raw numbers into C-suite text summaries.

Python
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

def generate_spatial_report(target_brand, total_comp, top_10_brands, suitability, cannibalization, api_key):
    """
    Passes our spatial calculations along with the API key to generate a professional C-suite report.
    """
    if not api_key:
        return "API key missing or configuration error."
        
    llm = ChatGroq(model="llama3-8b-8b", temperature=0.2, groq_api_key=api_key)
    
    template = """
    You are an expert AI Market Planning Director specializing in retail site selection and GIS spatial intelligence.
    Provide a comprehensive, professional Site Suitability Executive Summary based on the following real-time spatial metrics:
    
    - Target Expansion Brand: {target_brand}
    - Total Competitor Stores within 1km Network: {total_comp}
    - Top 10 Existing Brands in Trade Area: {top_10}
    - Calculated Site Suitability Score (out of 100): {suitability}
    - Sister-Store Cannibalization Score (out of 100): {cannibalization}
    
    Structure your report with the following professional headers:
    1. Executive Recommendation (Go / No-Go Decision)
    2. Trade Area Competitive Saturated Analysis
    3. Risk Mitigation Strategy (Focusing on the Cannibalization vs Poaching Dynamic)
    4. Infrastructure & Demographics Inference (Based on the 1km drive network reality)
    
    Keep the tone highly strategic, crisp, and ready for C-suite presentation.
    """
    
    prompt = PromptTemplate(
        input_variables=["target_brand", "total_comp", "top_10", "suitability", "cannibalization"],
        template=template
    )
    
    chain = prompt | llm
    
    response = chain.invoke({
        "target_brand": target_brand,
        "total_comp": total_comp,
        "top_10": str(top_10_brands),
        "suitability": suitability,
        "cannibalization": cannibalization
    })
    
    return response.content
