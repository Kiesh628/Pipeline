import io
import json
import math
import re
import zipfile
from pathlib import Path

import requests
from ladybug.epw import EPW

from consts import WEATHER_FILE_FOLDER, WEATHER_URL

def create_weather_folder() -> Path:
    WEATHER_FILE_FOLDER.mkdir(parents=True, exist_ok=True)
    return WEATHER_FILE_FOLDER

def get_master_geojson() -> list[dict]:
    """
    Returns the list of GeoJSON features for EnergyPlus weather stations.
    Caches the master.geojson file locally to prevent redundant downloads.
    """
    folder = create_weather_folder()
    local_cache = folder / "master.geojson"
    
    if local_cache.exists():
        try:
            with open(local_cache, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("features", [])
        except Exception:
            pass  # Fall through to re-download if file is corrupted
            
    # Download from NREL GitHub
    response = requests.get(WEATHER_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    with open(local_cache, "w", encoding="utf-8") as f:
        json.dump(data, f)
        
    return data.get("features", [])

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance in kilometers between two lat/lon coordinates."""
    r = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c

def find_nearest_weather_stations(lat: float, lon: float, top_k: int = 3) -> list[dict]:
    """
    Finds the top_k nearest weather stations to the specified latitude and longitude.
    Returns dictionaries containing title, distance_km, epw_url, latitude, longitude.
    """
    features = get_master_geojson()
    candidates = []
    
    for feat in features:
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue
            
        f_lon, f_lat = float(coords[0]), float(coords[1])
        dist_km = haversine_distance(lat, lon, f_lat, f_lon)
        
        props = feat.get("properties", {})
        title = props.get("title", "Unknown Station")
        epw_html = props.get("epw", "")
        
        match = re.search(r'href=[\'"]?([^\'" >]+)', epw_html)
        if match:
            epw_url = match.group(1)
            candidates.append({
                "title": title,
                "distance_km": dist_km,
                "epw_url": epw_url,
                "latitude": f_lat,
                "longitude": f_lon
            })
            
    candidates.sort(key=lambda x: x["distance_km"])
    return candidates[:top_k]

def download_weather_file_from_url(download_url: str, safe_name: str | None = None) -> Path:
    """
    Downloads an EPW file given a direct download URL, unzipping if necessary.
    Validates the downloaded file with ladybug.epw.EPW.
    """
    create_weather_folder()
    
    if not safe_name:
        # Extract filename from URL
        safe_name = download_url.rstrip("/").split("/")[-1]
        if safe_name.lower().endswith(".zip"):
            safe_name = safe_name[:-4]
        if safe_name.lower().endswith(".epw"):
            safe_name = safe_name[:-4]
            
    safe_name = re.sub(r'[^a-zA-Z0-9_\-.]', '_', safe_name)
    file_path = WEATHER_FILE_FOLDER / f"{safe_name}.epw"
    
    if file_path.exists():
        return file_path.absolute()
        
    response = requests.get(download_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
    response.raise_for_status()
    
    # Unzip if zip file
    if download_url.lower().endswith('.zip') or 'application/zip' in response.headers.get('Content-Type', ''):
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            epw_filename = next((name for name in z.namelist() if name.lower().endswith('.epw')), None)
            if not epw_filename:
                raise FileNotFoundError("Downloaded zip file does not contain an .epw file.")
            file_data = z.read(epw_filename)
    else:
        file_data = response.content
        
    with open(file_path, 'wb') as out_file:
        out_file.write(file_data)
        
    try:
        EPW(str(file_path.absolute()))
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise ValueError(f"Downloaded EPW file is corrupted or invalid: {e}")
        
    return file_path.absolute()

def get_download_url(city_name: str) -> str:
    search_term = city_name.lower().replace(' ', '')
    features = get_master_geojson()
    
    for feature in features:
        properties = feature.get("properties", {})
        epw_html = properties.get("epw", "")
        match = re.search(r'href=[\'"]?([^\'" >]+)', epw_html)
        
        if match:
            download_url = match.group(1)
            if search_term in download_url.lower().replace("_", "").replace("-", "").replace(".", ""):
                return download_url
                
    raise ValueError(f"Could not find an EPW file for '{city_name}'. Database unreachable.")

def get_weather_file(city_name: str) -> Path:
    create_weather_folder()
    
    safe_name = city_name.lower().replace(' ', '_')
    file_path = WEATHER_FILE_FOLDER / f"{safe_name}.epw"
    
    if file_path.exists():
        return file_path.absolute()

    download_url = get_download_url(city_name)
    return download_weather_file_from_url(download_url, safe_name)

if __name__ == "__main__":
    stations = find_nearest_weather_stations(51.50015, -0.12599, top_k=3)
    for s in stations:
        print(f"{s['title']} ({s['distance_km']:.1f} km) -> {s['epw_url']}")