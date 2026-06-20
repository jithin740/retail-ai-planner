import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

ox.settings.use_cache = True
ox.settings.log_console = False
ox.settings.user_agent = "RetailAIPlannerAgent/1.0 (contact: marketplanning@domain.com)"

def get_drive_time_buffer(lat, lon, distance_km=1.0, speed_kmh=30.0):
    """
    Calculates a real 1 km drive-time zone and returns both the Polygon 
    and a perfectly ordered exterior ring for a clean map outline.
    """
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

def fetch_competitors(isochrone_polygon):
    """
    Finds all retail/food brands inside the boundary, groups them cleanly by category,
    and drops geometry duplicates to ensure crisp numbers.
    """
    tags = {'amenity': ['fast_food', 'restaurant', 'cafe'], 'shop': ['supermarket', 'mall', 'clothes']}
    poi_list = []
    
    try:
        gdf = ox.features_from_polygon(isochrone_polygon, tags=tags)
        if gdf.empty:
            return pd.DataFrame(), {}, 0, []
        
        # Convert all polygons/lines into clean point centroids
        gdf['geometry'] = gdf.geometry.centroid
        
        # Parse crisp classification types
        gdf['category'] = gdf['amenity'].fillna(gdf['shop']).fillna('retail').str.replace('_', ' ').str.title()
        gdf['final_brand'] = gdf['brand'].fillna(gdf['name']).fillna('Independent Retailer')
        
        # Drop duplicates where identical store brands share overlapping location nodes
        gdf = gdf.drop_duplicates(subset=['final_brand', 'category', gdf['geometry'].x.round(5), gdf['geometry'].y.round(5)])
        
        # Extract metadata attributes for advanced hover tooltips
        for idx, row in gdf.iterrows():
            poi_list.append({
                "name": str(row['final_brand']),
                "lat": float(row['geometry'].y),
                "lon": float(row['geometry'].x),
                "category": str(row['category'])
            })
            
        # Create structural counts
        brand_counts = gdf['final_brand'].value_counts().to_dict()
        top_10 = dict(list(brand_counts.items())[:10])
        total_competition = len(gdf)
        
        # Keep clean columns for the dataframe table render
        df_clean = gdf[['final_brand', 'category']].rename(columns={'final_brand': 'Brand/Name', 'category': 'Category'}).reset_index(drop=True)
        
        return df_clean, top_10, total_competition, poi_list
    except Exception:
        return pd.DataFrame(), {}, 0, []

def calculate_market_scores(total_comp, target_brand, top_10_brands):
    """
    Looks for partial, case-insensitive string matches to track cannibalization.
    """
    internal_brand_count = 0
    target_clean = str(target_brand).strip().lower()
    
    for brand_name, count in top_10_brands.items():
        if target_clean in str(brand_name).lower():
            internal_brand_count += count
            
    cannibalisation_score = min(100, internal_brand_count * 35) 
    suitability_score = max(10, 90 - (total_comp * 2) - cannibalisation_score) # Dampened slightly due to deduplicated counts
    
    return suitability_score, cannibalisation_score
