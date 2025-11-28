from typing import Any, Dict, List, Optional, Callable, Type
from pydantic import BaseModel, Field
import json

class ToolResult(BaseModel):
    """
    Standardized output from any tool execution.
    """
    status: str = Field(..., description="Result status: 'success', 'failed', 'error'")
    data: Any = Field(default=None, description="The actual payload/data returned by the tool")
    summary: str = Field(default="", description="A brief summary for the LLM to digest")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    cost: float = Field(default=0.0, description="Estimated cost/tokens used")

class ToolDefinition(BaseModel):
    """
    Metadata defining a tool for the Planner.
    """
    name: str
    description: str
    input_schema: Dict[str, Any] # JSON Schema definition
    capabilities: List[str] = Field(default_factory=list)
    func: Optional[Callable] = None # The actual python function to call (not serialized)

    def to_schema(self) -> Dict[str, Any]:
        """
        Returns the OpenAI function calling / tool schema format.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema
            }
        }

class ToolRegistry:
    """
    Central registry for all available tools.
    """
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, input_model: Type[BaseModel], func: Callable, capabilities: List[str] = []):
        """
        Register a tool using a Pydantic model for input schema.
        """
        schema = input_model.model_json_schema()
        # Clean up schema for LLM (remove title, etc if needed)
        
        tool_def = ToolDefinition(
            name=name,
            description=description,
            input_schema=schema,
            capabilities=capabilities,
            func=func
        )
        self._tools[name] = tool_def
        # 🔑 使用分级日志，只在 VERBOSE 模式显示
        from utils.logger import log_debug
        log_debug(f"Tool Registered: {name}")

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def list_tool_schemas(self) -> List[Dict[str, Any]]:
        return [t.to_schema() for t in self._tools.values()]

# Global Registry Instance
registry = ToolRegistry()

