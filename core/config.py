import yaml
import os
from typing import Dict, Any

def load_settings() -> Dict[str, Any]:
    path = os.path.join("config", "settings.yaml")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

