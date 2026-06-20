import requests

def geocode_location(query_string):
    """
    Translates a text address string into [lat, lon] coordinates 
    using the free OpenStreetMap Nominatim API.
    """
    if not query_string or len(query_string.strip()) < 3:
        return None
        
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "RetailAIPlannerGeocoder/1.0 (contact: marketplanning@domain.com)"}
    params = {"q": query_string, "format": "json", "limit": 1}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200 and len(response.json()) > 0:
            location_data = response.json()[0]
            return [float(location_data["lat"]), float(location_data["lon"])]
    except Exception:
        pass
    return None
