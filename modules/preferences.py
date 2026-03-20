import json
import os

PREFERENCE_JSON = "preferences.json"
DEFAULT_PREFERENCE_JSON = "default_preferences.json"

def set_preference(attr, value):
    data = {}
    if os.path.exists(PREFERENCE_JSON):
        with open(PREFERENCE_JSON, "r") as fh:
            data = json.load(fh)
    data[attr] = value
    with open(PREFERENCE_JSON, "w") as fh:
        json.dump(data, fh, indent=4)

def get_preference(attr):
    default_data = {}
    with open(DEFAULT_PREFERENCE_JSON, "r") as fh:
        default_data = json.load(fh)
    if os.path.exists(PREFERENCE_JSON):
        data = {}
        with open(PREFERENCE_JSON, "r") as fh:
            data = json.load(fh)
        if attr in data:
            return data[attr]
    return default_data[attr]