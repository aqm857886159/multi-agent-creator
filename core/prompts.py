import os
import yaml
from typing import Dict, Any

def load_prompts() -> Dict[str, Any]:
    path = os.path.join("config", "prompts.yaml")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_prompt(agent_name: str) -> Dict[str, Any]:
    """Helper to get a specific agent's prompt config"""
    data = load_prompts()
    return data.get(agent_name, {})
