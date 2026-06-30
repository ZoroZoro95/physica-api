import json
import os
from typing import Optional
from groq import Groq
from .v2_models import PhysicsFacts

PROMPT_V2_PARSER = """
You are a physics parser. Your goal is to extract strictly factual information from a projectile motion question.
Do NOT solve the problem. Do NOT guess animation steps.
Output exactly one JSON object matching the requested schema.

Extract:
- objects: The particles/bodies involved (e.g. id "P", type "particle")
- surfaces: The physical boundaries (e.g. incline, ground, wall)
- actions: What happens to objects initially (e.g. "projected", "released_from_rest")
- events: Key milestones (e.g. "collision", "lands")
- known_values: Dictionary of given numerical values (e.g. "g": 10)
- unknown: What needs to be calculated (e.g. symbol "u", quantity "initial_speed_of_P")

Output JSON strictly matching this schema:
{
  "objects": [{"id": "str", "type": "str"}],
  "surfaces": [{"id": "str", "type": "str", "angle_deg": float, "smooth": bool}],
  "actions": [{"object_id": "str", "type": "str", "direction": "str", "speed": "str", "surface_id": "str"}],
  "events": [{"type": "str", "objects": ["str"], "time_sec": float}],
  "known_values": {"str": "any"},
  "unknown": {"symbol": "str", "quantity": "str"}
}
"""

class V2PhysicsParser:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key required for V2 Parser.")
        self.client = Groq(api_key=self.api_key)
        self.model = "llama-3.3-70b-versatile"

    def parse_question(self, text: str) -> PhysicsFacts:
        """Extracts physics facts from question text."""
        try:
            return self._call_llm(text)
        except Exception as e:
            print(f"[V2Parser] First attempt failed: {e}. Retrying...")
            return self._call_llm(text)

    def _call_llm(self, text: str) -> PhysicsFacts:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": PROMPT_V2_PARSER},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = response.choices[0].message.content
        return PhysicsFacts.model_validate_json(content)
