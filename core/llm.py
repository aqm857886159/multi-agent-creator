import os
import yaml
import logging
import json
import re
from typing import Optional, Dict, Any, Type, TypeVar
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Instructor Imports
import instructor
from openai import OpenAI
from pydantic import BaseModel

# Load Configuration
def load_model_config() -> Dict[str, Any]:
    path = os.path.join("config", "models.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError("config/models.yaml not found!")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

_MODEL_CONFIG = load_model_config()
T = TypeVar("T", bound=BaseModel)

class ModelGateway:
    """
    Abstraction layer for LLM interactions (The 'Macro' Level Routing).
    Handles:
    - Capability Mapping (e.g., 'creative' -> Kimi, 'fast' -> DeepSeek)
    - OpenRouter Specific Headers (Ops Level Observability)
    - Execution Helpers (call, call_as_json, call_with_schema)
    """
    
    def __init__(self):
        self.config = _MODEL_CONFIG
        # Prioritize LLM_* env vars, fallback to OPENAI_* for backward compatibility
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL") or "https://openrouter.ai/api/v1"
        
        if not self.api_key:
            logging.warning("LLM_API_KEY not set. LLM calls will fail.")

        # Initialize Instructor Client (Patched OpenAI)
        self.instructor_client = instructor.from_openai(
            OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                default_headers={
                    "HTTP-Referer": self.config["openrouter"].get("site_url", ""),
                    "X-Title": self.config["openrouter"].get("site_name", "Topic Radar")
                }
            ),
            mode=instructor.Mode.JSON # Force JSON mode for broad compatibility
        )

    def _get_model_params(self, capability: str) -> Dict[str, Any]:
        """Helper to get model config params"""
        # 映射：把 planner 映射到 reasoning，把 worker 映射到 fast
        if capability == "planner": capability = "reasoning"
        if capability == "worker": capability = "fast"
            
        agent_config = self.config["models"].get(capability)
        
        # 用户要求：绝对不使用默认值，完全依赖配置文件
        if not agent_config:
            raise ValueError(f"❌ Configuration Error: Capability '{capability}' is not defined in config/models.yaml")
            
        return agent_config

    def get_llm(self, capability: str = "creative") -> ChatOpenAI:
        """
        Factory method to get a configured LangChain ChatModel based on capability.
        Used for unstructured chat.
        """
        agent_config = self._get_model_params(capability)
        
        headers = {
            "HTTP-Referer": self.config["openrouter"].get("site_url", ""),
            "X-Title": self.config["openrouter"].get("site_name", "Topic Radar")
        }

        llm = ChatOpenAI(
            model=agent_config["model_id"],
            openai_api_key=self.api_key,
            openai_api_base=self.base_url,
            temperature=agent_config.get("temperature", 0.7),
            max_tokens=agent_config.get("max_tokens", 1000),
            request_timeout=agent_config.get("timeout", 60),
            model_kwargs={"extra_headers": headers}
        )
        return llm

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def call(self, prompt: str, system_prompt: str = "You are a helpful assistant.", capability: str = "fast") -> str:
        """Simple text generation"""
        llm = self.get_llm(capability)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = llm.invoke(messages)
        return self._clean_thinking(response.content)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def call_as_json(self, user_prompt: str, system_prompt: str = "You are a JSON generator.", capability: str = "fast") -> Dict[str, Any]:
        """
        Legacy JSON generation (String parsing). 
        DEPRECATED: Use call_with_schema instead.
        """
        # ... existing implementation kept for backward compatibility ...
        return self._legacy_call_as_json(user_prompt, system_prompt, capability)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def call_with_schema(self, user_prompt: str, schema_model: Type[T], system_prompt: str = "You are a helpful assistant.", capability: str = "fast") -> T:
        """
        Generates structured output strictly adhering to a Pydantic model.
        Uses 'instructor' library for robust validation and retries.
        """
        agent_config = self._get_model_params(capability)
        model_id = agent_config["model_id"]
        
        try:
            # Instructor automatically handles validation loops
            response = self.instructor_client.chat.completions.create(
                model=model_id,
                response_model=schema_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=agent_config.get("temperature", 0.7),
                max_tokens=agent_config.get("max_tokens", 1000),
            )
            return response
        except Exception as e:
            logging.error(f"❌ LLM Schema Call Failed: {e}")
            # Rethrow to let tenacity handle retries, or let caller handle fallback
            raise e

    def _legacy_call_as_json(self, user_prompt, system_prompt, capability):
        # ... (Original implementation moved here)
        llm = self.get_llm(capability)
        json_instruction = "\nIMPORTANT: Return ONLY valid JSON. No markdown formatting, no code blocks."
        messages = [
            SystemMessage(content=system_prompt + json_instruction),
            HumanMessage(content=user_prompt)
        ]
        response = llm.invoke(messages)
        content = self._clean_thinking(response.content).strip()
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"JSON Decode Error. Raw output: {content[:100]}...")
            return {}

    def _clean_thinking(self, text: str) -> str:
        """Removes <think> tags"""
        if not text: return ""
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return cleaned.strip()

# Singleton instance
_GATEWAY = ModelGateway()

def get_llm(capability: str = "creative"):
    return _GATEWAY.get_llm(capability)

# Expose wrapper functions for easier import
def get_llm_with_schema(user_prompt: str, response_model: Type[T], system_prompt: str = "You are a helpful assistant.", capability: str = "fast") -> T:
    return _GATEWAY.call_with_schema(user_prompt, response_model, system_prompt, capability)
