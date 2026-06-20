import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

ox.settings.use_cache = True
ox.settings.log_console = False

def get_drive_time_buffer(lat, lon, distance_km=1.0, speed_kmh=30.0):
    """
    Calculates a real 1 km drive-time zone and returns both the Polygon 
    and a perfectly ordered exterior ring for a clean map outline.
    """
    time_limit_seconds = (distance_km / speed_kmh) * 3600
    
    # Fetch street grid
    graph = ox.graph_from_point((lat, lon), dist=distance_km * 1200, network_type='drive')
    graph = ox.routing.add_edge_speeds(graph)
    graph = ox.routing.add_edge_travel_times(graph)
    
    center_node = ox.nearest_nodes(graph, X=lon, Y=lat)
    subgraph = nx.ego_graph(graph, center_node, radius=time_limit_seconds, distance='travel_time')
    
    node_points = [Point(data['x'], data['y']) for node, data in subgraph.nodes(data=True)]
    isochrone_poly = Polygon([[p.x, p.y] for p in node_points]).convex_hull
    
    # FIX: Get the perfectly ordered outer shell coordinates from the convex hull polygon
    if isinstance(isochrone_poly, Polygon):
        x, y = isochrone_poly.exterior.coords.xy
        boundary_coords = [[lat_val, lon_val] for lon_val, lat_val in zip(x, y)]
    else:
        boundary_coords = [[p.y, p.x] for p in node_points]
    
    return isochrone_poly, boundary_coords

def fetch_competitors(isochrone_polygon):
    """
    Finds all retail/food brands inside the boundary, extracts their precise 
    coordinates, and groups them cleanly.
    """
    tags = {'amenity': ['fast_food', 'restaurant', 'cafe'], 'shop': ['supermarket', 'mall', 'clothes']}
    poi_list = []
    
    try:
        gdf = ox.features_from_polygon(isochrone_polygon, tags=tags)
        if gdf.empty:
            return pd.DataFrame(), {}, 0, []
        
        gdf['geometry'] = gdf.geometry.centroid
        gdf['final_brand'] = gdf['brand'].fillna(gdf['name']).fillna('Independent Retailer')
        
        # Build a clean list of dictionaries containing coordinates for map markers
        for idx, row in gdf.iterrows():
            poi_list.append({
                "name": row['final_brand'],
                "lat": row['geometry'].y,
                "lon": row['geometry'].x,
                "type": row.get('amenity', row.get('shop', 'retail'))
            })
            
        brand_counts = gdf['final_brand'].value_counts().to_dict()
        top_10 = dict(list(brand_counts.items())[:10])
        total_competition = len(gdf)
        
        return gdf, top_10, total_competition, poi_list
    except Exception:
        return pd.DataFrame(), {}, 0, []

def calculate_market_scores(total_comp, target_brand, top_10_brands):
    """
    Fixed Cannibalization Logic: Looks for partial, case-insensitive string matches 
    to make sure existing sister branches are detected properly.
    """
    internal_brand_count = 0
    target_clean = str(target_brand).strip().lower()
    
    # Loop over nearby brands and check if your brand string is hidden inside them
    for brand_name, count in top_10_brands.items():
        if target_clean in str(brand_name).lower():
            internal_brand_count += count
            
    cannibalisation_score = min(100, internal_brand_count * 35) 
    suitability_score = max(10, 90 - (total_comp * 4) - cannibalisation_score)
    
    return suitability_score, cannibalisation_score
