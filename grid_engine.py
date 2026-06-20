import math
import pandas as pd
from shapely.geometry import Polygon, Point

def generate_hexagonal_grid(aoi_polygon, center_lat, grid_size_meters):
    """
    Generates regular hexagonal grid cells that tightly intersect 
    the 1 km drive-time Area of Interest (AOI).
    """
    # High-accuracy degree conversion factors for Southern/Central India grid scales
    lat_degree_meters = 111132.0
    lon_degree_meters = 111132.0 * math.cos(math.radians(center_lat))
    
    # Calculate radius dimensions in spatial degrees
    r_lat = grid_size_meters / lat_degree_meters
    r_lon = grid_size_meters / lon_degree_meters
    
    min_lon, min_lat, max_lon, max_lat = aoi_polygon.bounds
    
    # Set up hexagonal horizontal and vertical grid spacing offsets
    width_spacing = math.sqrt(3) * r_lon
    height_spacing = 1.5 * r_lat
    
    columns = int(math.ceil((max_lon - min_lon) / width_spacing)) + 2
    rows = int(math.ceil((max_lat - min_lat) / height_spacing)) + 2
    
    hexagons = []
    
    for row in range(rows):
        current_lat = min_lat + (row * height_spacing)
        # Shift every second row horizontally to form the overlapping honeycomb pattern
        col_offset = (width_spacing / 2.0) if (row % 2 == 1) else 0.0
        
        for col in range(columns):
            current_lon = min_lon + (col * width_spacing) + col_offset
            
            # Construct 6 sequential vertices of a regular hexagon
            vertices = []
            for i in range(6):
                angle_deg = 60 * i + 30
                angle_rad = math.pi / 180 * angle_deg
                v_lon = current_lon + r_lon * math.cos(angle_rad)
                v_lat = current_lat + r_lat * math.sin(angle_rad)
                vertices.append((v_lon, v_lat))
                
            hex_poly = Polygon(vertices)
            
            # Only retain grid cells that directly clip our true drive-time network area
            if aoi_polygon.intersects(hex_poly):
                hexagons.append(hex_poly)
                
    return hexagons

def rank_hexagonal_grids(hex_polygons, poi_list, category_weights):
    """
    Aggregates point criteria inside every hexagonal unit cell, applies 
    user-defined weight indices, and ranks cells by structural favorability.
    """
    grid_data = []
    
    for idx, hex_cell in enumerate(hex_polygons):
        score = 0.0
        poi_counts_by_cat = {}
        total_pois_in_cell = 0
        
        # Scan all spatial nodes inside this specific grid coordinate block
        for poi in poi_list:
            pt = Point(poi["lon"], poi["lat"])
            if hex_cell.contains(pt):
                cat = poi["category"]
                poi_counts_by_cat[cat] = poi_counts_by_cat.get(cat, 0) + 1
                total_pois_in_cell += 1
                
                # Apply criteria optimization weights passed from sliders/inputs
                weight = category_weights.get(cat, 0.0) / 100.0
                score += (1.0 * weight)
                
        # Format clean sequential coordinates [[lat, lon], ...] for Folium mapping loops
        x, y = hex_cell.exterior.coords.xy
        boundary_locations = [[lat_val, lon_val] for lon_val, lat_val in zip(x, y)]
        
        centroid = hex_cell.centroid
        
        grid_data.append({
            "grid_id": idx,
            "boundary_locations": boundary_locations,
            "centroid_lat": centroid.y,
            "centroid_lon": centroid.x,
            "score": score,
            "total_density": total_pois_in_cell,
            "breakdown": poi_counts_by_cat
        })
        
    # Sort data directly by suitability score descending
    df_grid = pd.DataFrame(grid_data)
    if df_grid.empty:
        return []
        
    df_grid = df_grid.sort_values(by="score", ascending=False).reset_index(drop=True)
    
    # Map explicit corporate ranks (Rank 1 = Top Location Asset)
    df_grid["rank"] = df_grid.index + 1
    
    return df_grid.to_dict(orient="records")
