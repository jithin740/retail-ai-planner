import h3
import pandas as pd
from shapely.geometry import Point, Polygon

def generate_h3_grid(aoi_polygon, h3_resolution):
    """
    Polyfills the 1 km drive-time catchment network polygon using 
    standardized Uber H3 hex spatial cells at the specified resolution.
    """
    # Format the shapely geometry interface explicitly for Uber H3 polyfill ingestion
    geo_json_poly = aoi_polygon.__geo_interface__
    
    try:
        # Support both H3 v3 (polyfill) and H3 v4 (polygon_to_cells) syntax structures smoothly
        if hasattr(h3, 'polygon_to_cells'):
            h3_hexes = h3.polygon_to_cells(geo_json_poly, h3_resolution)
        else:
            h3_hexes = h3.polyfill(geo_json_poly, h3_resolution, geo_json=True)
    except Exception:
        # Fallback handling for specific geo-interface coordinate orderings
        exterior_coords = list(aoi_polygon.exterior.coords)
        # H3 expects standard [[lat, lon], ...] sequences for loops
        formatted_coords = [[lat, lon] for lon, lat in exterior_coords]
        
        if hasattr(h3, 'polygon_to_cells'):
            h3_hexes = h3.polygon_to_cells(formatted_coords, h3_resolution)
        else:
            h3_hexes = h3.polyfill({"type": "Polygon", "coordinates": [exterior_coords]}, h3_resolution, geo_json=True)

    hex_cells = list(h3_hexes)
    return hex_cells

def rank_h3_grids(h3_hexes, poi_list, category_weights):
    """
    Maps commercial points to respective H3 cells, applies user priority 
    weight indices, and generates exact percentile ranks.
    """
    grid_data = []
    
    for idx, hex_id in enumerate(h3_hexes):
        score = 0.0
        poi_counts_by_cat = {}
        total_pois_in_cell = 0
        
        # Get outer ring vertex boundary tracks formatted for Folium [[lat, lon], ...]
        vertices = h3.h3_to_geo_boundary(hex_id)
        boundary_locations = [[lat, lon] for lat, lon in vertices]
        
        # Extract cell center point coordinate locations
        centroid_lat, centroid_lon = h3.h3_to_geo(hex_id)
        hex_cell_shape = Polygon([[lon, lat] for lat, lon in boundary_locations])
        
        for poi in poi_list:
            pt = Point(poi["lon"], poi["lat"])
            if hex_cell_shape.contains(pt):
                cat = poi["category"]
                poi_counts_by_cat[cat] = poi_counts_by_cat.get(cat, 0) + 1
                total_pois_in_cell += 1
                
                weight = category_weights.get(cat, 0.0) / 100.0
                score += (1.0 * weight)
                
        grid_data.append({
            "grid_id": str(hex_id),
            "boundary_locations": boundary_locations,
            "centroid_lat": centroid_lat,
            "centroid_lon": centroid_lon,
            "score": score,
            "total_density": total_pois_in_cell,
            "breakdown": poi_counts_by_cat
        })
        
    df_grid = pd.DataFrame(grid_data)
    if df_grid.empty:
        return []
        
    # Order grids securely by performance scores descending
    df_grid = df_grid.sort_values(by="score", ascending=False).reset_index(drop=True)
    df_grid["rank"] = df_grid.index + 1
    
    total_cells = len(df_grid)
    
    # Calculate exact percentile distributions for color ramp partitioning
    if total_cells > 0:
        df_grid["percentile"] = (total_cells - df_grid["rank"]) / total_cells
    else:
        df_grid["percentile"] = 0.0
        
    return df_grid.to_dict(orient="records")
