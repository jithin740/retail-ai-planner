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
        fallback_poly = Point(lon, lat).buffer(0.009)
        x, y = fallback_poly.exterior.coords.xy
        boundary_coords = [[lat_val, lon_val] for lon_val, lat_val in zip(x, y)]
        return fallback_poly, boundary_coords

def fetch_competitors(lat, lon, isochrone_polygon):
    """
    Direct Overpass API stream: Bypasses library parsing loops by 
    pulling raw JSON data directly from OpenStreetMap servers.
    """
    poi_list = []
    
    # Create a stable 1.5km bounding search box around your clicked coordinates
    bbox = f"{lat - 0.015},{lon - 0.015},{lat + 0.015},{lon + 0.015}"
    
    # Formulate pure Overpass QL Query
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
            # Handle standard nodes and multi-node structural centroids safely
            p_lat = el['center']['lat'] if 'center' in el else el.get('lat')
            p_lon = el['center']['lon'] if 'center' in el else el.get('lon')
            
            if p_lat is None or p_lon is None:
                continue
                
            # Perform local point-in-polygon verification against your exact driving network boundaries
            pt = Point(p_lon, p_lat)
            if not isochrone_polygon.contains(pt):
                continue
                
            tags = el.get('tags', {})
            amenity = tags.get('amenity')
            shop = tags.get('shop')
            
            # Format clean strings
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
        # Deduplicate overlapping nodes in close proximity
        df = df.drop_duplicates(subset=['Brand/Name', 'Category', df['lon'].round(4), df['lat'].round(4)])
        
        # Build UI dictionary array with correct lowercase object targets
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
    internal_brand_count = 0
    target_clean = str(target_brand).strip().lower()
    
    for brand_name, count in top_10_brands.items():
        if target_clean in str(brand_name).lower():
            internal_brand_count += count
            
    cannibalisation_score = min(100, internal_brand_count * 35) 
    suitability_score = max(10, 90 - (total_comp * 2) - cannibalisation_score)
    
    return suitability_score, cannibalisation_score
