import json
import os

def generate_soil_mapping():
    # Load the downloaded districts json
    with open('indian_districts.json', 'r') as f:
        data = json.load(f)

    # Base State -> Soil mapping
    state_soil_map = {
        "punjab": "Alluvial Soil",
        "haryana": "Alluvial Soil",
        "uttar pradesh": "Alluvial Soil",
        "bihar": "Alluvial Soil",
        "west bengal": "Alluvial Soil",
        "assam": "Alluvial Soil",
        "maharashtra": "Black Soil",
        "gujarat": "Black Soil",
        "madhya pradesh": "Black Soil",
        "andhra pradesh": "Red Soil",
        "telangana": "Red Soil",
        "karnataka": "Red Soil",
        "tamil nadu": "Red Soil",
        "odisha": "Red Soil",
        "chhattisgarh": "Red Soil",
        "jharkhand": "Red Soil",
        "kerala": "Laterite Soil",
        "goa": "Laterite Soil",
        "rajasthan": "Desert Soil",
        "himachal pradesh": "Mountain Soil",
        "uttarakhand": "Mountain Soil",
        "jammu and kashmir": "Mountain Soil",
        "sikkim": "Mountain Soil",
        "arunachal pradesh": "Mountain Soil",
        "meghalaya": "Laterite Soil",
        "mizoram": "Red Soil",
        "nagaland": "Red Soil",
        "manipur": "Red Soil",
        "tripura": "Red Soil",
        "chandigarh": "Alluvial Soil",
        "delhi": "Alluvial Soil",
        "puducherry": "Laterite Soil"
    }

    # Specific District Overrides (Coastal/Hilly areas that differ from their state's primary soil)
    district_overrides = {
        "dakshina kannada": "Laterite Soil",
        "udupi": "Laterite Soil",
        "uttara kannada": "Laterite Soil",
        "ratnagiri": "Laterite Soil",
        "sindhudurg": "Laterite Soil",
        "darjeeling": "Mountain Soil",
        "kutch": "Desert Soil"
    }

    districts_map = {}
    
    for state_data in data.get('states', []):
        state_name = state_data['state'].lower()
        state_soil = state_soil_map.get(state_name, "Alluvial Soil") # fallback
        
        for district in state_data.get('districts', []):
            dist_lower = district.lower()
            # If district has an override, use it, else use state's soil
            districts_map[dist_lower] = district_overrides.get(dist_lower, state_soil)
            
    # Add a few manual aliases that people might type
    districts_map["puttur"] = "Laterite Soil"
    districts_map["mangalore"] = "Laterite Soil"
    districts_map["karwar"] = "Laterite Soil"

    final_mapping = {
        "districts": districts_map,
        "states": state_soil_map,
        "default": "Alluvial Soil"
    }

    # Write back to geo_soil_mapping.json
    output_path = 'app/data/geo_soil_mapping.json'
    with open(output_path, 'w') as f:
        json.dump(final_mapping, f, indent=2)
        
    print(f"✅ Generated {len(districts_map)} district mappings and {len(state_soil_map)} state mappings.")
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    generate_soil_mapping()
