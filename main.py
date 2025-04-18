from flask import Flask, jsonify
import requests
from datetime import datetime, UTC
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ✅ Define NOAA API URL for cyclone data
NOAA_URL = "https://api.weather.gov/products/types/TCM"  # Replace with actual NOAA API for live cyclone data
MODEL_ENDPOINT = "https://your-model-api-url.com/predict_cluster"  # Replace with your model's API

# ✅ USGS API for Earthquake Data
USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
 
# Global variables to store latest data
latest_earthquake_data = []
latest_cyclone_data = []

def fetch_earthquake_data():
    """Fetch latest earthquake data from USGS with comprehensive details."""
    global latest_earthquake_data

    params = {
        "format": "geojson",
        "starttime": datetime.now(UTC).strftime('%Y-%m-%d'),
        "endtime": datetime.now(UTC).strftime('%Y-%m-%d'),
        "minmagnitude": 3.0,
        "orderby": "time-asc",  # Get oldest first
        "limit": 50,
        "eventtype": "earthquake"
    }

    try:
        response = requests.get(USGS_URL, params=params)
        
        if response.status_code == 200:
            data = response.json()
            extracted_data = []

            for feature in data["features"]:
                properties = feature["properties"]
                geometry = feature["geometry"]["coordinates"]
                
                # Extract detailed location information
                place = properties.get("place", "N/A")
                if ", " in place:
                    region = place.split(", ")[-1]  # Get the region/country
                else:
                    region = place
                
                # Comprehensive earthquake information
                earthquake_info = {
                    # Basic info
                    "id": feature.get("id"),
                    "time": properties.get("time"),
                    "updated": properties.get("updated"),
                    
                    # Magnitude details
                    "magnitude": properties.get("mag"),
                    "mag_type": properties.get("magType"),
                    "magnitude_error": properties.get("magError", "N/A"),
                    
                    # Location details
                    "latitude": geometry[1],
                    "longitude": geometry[0],
                    "depth_km": geometry[2],
                    "depth_error": properties.get("depthError", "N/A"),
                    "location": place,
                    "region": region,
                    
                    # Seismic parameters
                    "seismic_stations": properties.get("nst", "N/A"),
                    "rms": properties.get("rms", "N/A"),  # Root mean square of travel time residuals
                    "gap": properties.get("gap", "N/A"),    # Azimuthal gap between stations
                    "dmin": properties.get("dmin", "N/A"),  # Horizontal distance to nearest station
                    
                    # Fault mechanism
                    "focal_mechanism": {
                        "strike": properties.get("strike", "N/A"),
                        "dip": properties.get("dip", "N/A"),
                        "rake": properties.get("rake", "N/A")
                    },
                    
                    # Tsunami risk
                    "tsunami_alert": 1 if properties.get("tsunami") else 0,
                    "tsunami_warning": properties.get("alert", "N/A"),  # "green", "yellow", "red"
                    
                    # Additional metadata
                    "event_type": properties.get("type"),
                    "status": properties.get("status"),  # "automatic" or "reviewed"
                    "url": properties.get("url")  # USGS detail page
                }

                extracted_data.append(earthquake_info)

            latest_earthquake_data = extracted_data
            print(f"[{datetime.now(UTC)}] ✅ Updated earthquake data ({len(extracted_data)} records)")
        else:
            print(f"❌ Failed to fetch earthquake data: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Error fetching earthquake data: {str(e)}")

def fetch_cyclone_data():
    """Fetch live cyclone data from NOAA."""
    global latest_cyclone_data

    try:
        response = requests.get(NOAA_URL)
        if response.status_code == 200:
            data = response.json().get("activeStorms", [])
            extracted_data = []

            for storm in data:
                storm_info = {
                    "ISO_TIME": storm.get("lastUpdate"),
                    "LAT": storm.get("latitude_numeric"),
                    "LON": storm.get("longitude_numeric"),
                    "STORM_SPEED": storm.get("movementSpeed"),
                    "STORM_DIR": storm.get("movementDir")
                }
                extracted_data.append(storm_info)

            latest_cyclone_data = extracted_data
            print(f"[{datetime.now(UTC)}] ✅ Updated cyclone data ({len(extracted_data)} records)")
        else:
            print(f"❌ Failed to fetch cyclone data: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Error fetching cyclone data: {e}")

def send_data_to_model():
    """Send live cyclone data to ML model."""
    if not latest_cyclone_data:
        print("⚠️ No cyclone data available.")
        return

    for storm in latest_cyclone_data:
        try:
            response = requests.post(MODEL_ENDPOINT, json=storm)
            print(f"✅ Sent cyclone data to model: {response.status_code}")
        except Exception as e:
            print(f"❌ Error sending cyclone data: {e}")

# 🔁 Combined scheduler-based approach
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_earthquake_data, "interval", minutes=10)
scheduler.add_job(fetch_cyclone_data, "interval", minutes=10)
scheduler.add_job(send_data_to_model, "interval", minutes=10)
scheduler.start()

# 🧪 Flask endpoints for manual access/testing
@app.route('/get_earthquake_data', methods=['GET'])
def get_earthquake_data():
    return jsonify(latest_earthquake_data)

@app.route('/get_cyclone_data', methods=['GET'])
def get_cyclone_data():
    return jsonify(latest_cyclone_data)

@app.route('/send_to_model', methods=['GET'])
def trigger_model_send():
    send_data_to_model()
    return jsonify({"message": "Cyclone data sent to model."})

if __name__ == '__main__':
    fetch_earthquake_data()  # Initial fetch
    fetch_cyclone_data()     # Initial fetch
    app.run(debug=True, port=5001)
