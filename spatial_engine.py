import osmnx as ox
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

# Tell the system to cache maps so it runs fast during your interview
ox.settings.use_cache = True
ox.settings.log_console = False

def get_drive_time_buffer(lat, lon, distance_km=1.0, speed_kmh=30.0):
    """
    Calculates a real 1 km drive-time zone using actual street networks.
    """
    # 1 km at 30 km/h takes about 120 seconds (2 minutes)
    time_limit_seconds = (distance_km / speed_kmh) * 3600
    
    # 1. Download the local street network around your coordinates
    graph = ox.graph_from_point((lat, lon), dist=distance_km * 1200, network_type='drive')
    
    # Updated modern syntax for speed/travel time calculation
    graph = ox.routing.add_edge_speeds(graph)
    graph = ox.routing.add_edge_travel_times(graph)
    
    # 2. Find the closest road intersection (updated safe method for newer osmnx)
    center_node = ox.nearest_nodes(graph, X=lon, Y=lat)
    
    # 3. Find all street points reachable within 2 minutes of driving
    subgraph = ox.ego_graph(graph, center_node, radius=time_limit_seconds, distance='travel_time')
    
    # 4. Connect those points together to form a boundary area (polygon)
    node_points = [Point(data['x'], data['y']) for node, data in subgraph.nodes(data=True)]
    isochrone_poly = Polygon([[p.x, p.y] for p in node_points]).convex_hull
    
    return isochrone_poly

def fetch_competitors(isochrone_polygon):
    """
    Finds all retail and food brands inside your drive-time boundary.
    """
    tags = {'amenity': ['fast_food', 'restaurant', 'cafe'], 'shop': ['supermarket', 'mall', 'clothes']}
    
    try:
        gdf = ox.features_from_polygon(isochrone_polygon, tags=tags)
        if gdf.empty:
            return pd.DataFrame(), {}, 0
        
        gdf['geometry'] = gdf.geometry.centroid
        gdf['final_brand'] = gdf['brand'].fillna(gdf['name']).fillna('Independent Retailer')
        
        brand_counts = gdf['final_brand'].value_counts().to_dict()
        top_10 = dict(list(brand_counts.items())[:10])
        total_competition = len(gdf)
        
        return gdf, top_10, total_competition
    except Exception:
        return pd.DataFrame(), {}, 0

def calculate_market_scores(total_comp, internal_brand_count):
    """
    Calculates analytical scores to show the interviewers.
    """
    cannibalisation_score = min(100, internal_brand_count * 35) 
    suitability_score = max(10, 90 - (total_comp * 4) - cannibalisation_score)
    
    return suitability_score, cannibalisation_score
