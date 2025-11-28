import yaml
import importlib
from typing import Dict, Any, Type
from pydantic import BaseModel
from core.tool_registry import registry, ToolDefinition
import os

def load_tools_from_config(config_path: str = "config/tools.yaml"):
    """
    Loads tool definitions from yaml and registers them in the global registry.
    Dynamically imports adapter classes and methods.
    """
    if not os.path.exists(config_path):
        print(f"⚠️ Tool config not found at {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config or "tools" not in config:
        return

    for tool_name, tool_info in config["tools"].items():
        try:
            # 1. Import Module
            module_path = tool_info["module"]
            module = importlib.import_module(module_path)
            
            # 2. Get Class and Instance
            class_name = tool_info["class"]
            cls = getattr(module, class_name)
            # Note: In a real prod env, we might want singleton instances or factory pattern
            # For now, we instantiate a new adapter for registration (or wrapper)
            # Actually, better to instantiate on execution or keep a singleton?
            # Let's create a wrapper function that instantiates on demand to save resources
            
            method_name = tool_info["method"]
            
            # 3. Get Input Model Class
            input_model_path = tool_info["input_model"]
            # input_model_path is like "tools.adapters.search_adapter.SearchInput"
            im_module_name, im_class_name = input_model_path.rsplit(".", 1)
            im_module = importlib.import_module(im_module_name)
            input_model_class = getattr(im_module, im_class_name)
            
            # 4. Create Wrapper Function
            def make_wrapper(cls_, method_name_, input_model_):
                def wrapper(params_dict: Dict[str, Any]):
                    # Instantiate adapter (could be optimized)
                    adapter = cls_() 
                    method = getattr(adapter, method_name_)
                    # Validate input
                    params_obj = input_model_(**params_dict)
                    return method(params_obj)
                return wrapper

            wrapper_func = make_wrapper(cls, method_name, input_model_class)
            
            # 5. Register
            registry.register(
                name=tool_name,
                description=tool_info["description"],
                input_model=input_model_class,
                func=wrapper_func,
                capabilities=tool_info.get("capabilities", [])
            )
            
        except Exception as e:
            print(f"❌ Failed to register tool {tool_name}: {e}")

# Load on import
load_tools_from_config()

