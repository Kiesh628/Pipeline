from pathlib import Path 

# Weather
WEATHER_FILE_FOLDER = Path(__file__).parent / "weather_data"
WEATHER_URL = "https://raw.githubusercontent.com/NREL/EnergyPlus/develop/weather/master.geojson"

# Buildings & Simulations
BUILDING_FILE_FOLDER = Path(__file__).parent / "building_energy_files"
SIMULATION_OUTPUT_FOLDER = Path(__file__).parent / "simulation_outputs"

