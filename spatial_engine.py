import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

# Global engine settings
ox.settings.use_cache = True
ox.settings.log_console = False
ox.settings.user_agent = "RetailAIPlannerAgent/1.0 (contact: marketplanning@domain.com)"

def get_drive_time_buffer(lat, lon, distance_km=1.0, speed_kmh=30.0):
    """
    Calculates a real 1 km drive-time zone and returns both the Polygon 
    and a clean outer boundary coordinate array for plotting.
    """
    try:
        time_limit_seconds = (distance_km / speed_kmh) * 3600
        
        # Download local street grid
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
        # Secure fallback polygon if the street graph calculation encounters an error
        fallback_poly = Point(lon, lat).buffer(0.009)
        x, y = fallback_poly.exterior.coords.xy
        boundary_coords = [[lat_val, lon_val] for lon_val, lat_val in zip(x, y)]
        return fallback_poly, boundary_coords

def fetch_competitors(lat, lon, isochrone_polygon):
    """
    Optimized: Fetches storefronts via a stable point-radius call,
    then clips them locally to your drive-time polygon boundary.
    """
    tags = {'amenity': ['fast_food', 'restaurant', 'cafe'], 'shop': ['supermarket', 'mall', 'clothes']}
    poi_list = []
    
    try:
        # Step 1: Use an ultra-stable point extraction query over a 1.2km buffer zone
        gdf = ox.features_from_point((lat, lon), tags=tags, dist=1200)
        if gdf.empty:
            return pd.DataFrame(columns=['Brand/Name', 'Category']), {}, 0, []
        
        # Step 2: Standardize geometries to centroids
        gdf['geometry'] = gdf.geometry.centroid
        
        # Step 3: Run local spatial filtering against the drive-time boundary shape
        gdf = gdf[gdf.geometry.apply(lambda point: isochrone_polygon.contains(point))]
        if gdf.empty:
            return pd.DataFrame(columns=['Brand/Name', 'Category']), {}, 0, []
        
        # Step 4: Ensure metadata target columns are present
        for column_tag in ['brand', 'name', 'amenity', 'shop']:
            if column_tag not in gdf.columns:
                gdf[column_tag] = None
        
        gdf['category'] = gdf['amenity'].fillna(gdf['shop']).fillna('Retail Store').astype(str).str.replace('_', ' ').str.title()
        gdf['final_brand'] = gdf['brand'].fillna(gdf['name']).fillna('Independent Retailer').astype(str)
        
        # Deduplicate immediate proximity storefront entries
        gdf = gdf.drop_duplicates(subset=['final_brand', 'category', gdf['geometry'].x.round(5), gdf['geometry'].y.round(5)])
        
        for idx, row in gdf.iterrows():
            poi_list.append({
                "name": str(row['final_brand']),
                "lat": float(row['geometry'].y),
                "lon": float(row['geometry'].x),
                "category": str(row['category'])
            })
            
        brand_counts = gdf['final_brand'].value_counts().to_dict()
        top_10 = dict(list(brand_counts.items())[:10])
        total_competition = len(gdf)
        
        df_clean = gdf[['final_brand', 'category']].rename(columns={'final_brand': 'Brand/Name', 'category': 'Category'}).reset_index(drop=True)
        
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
