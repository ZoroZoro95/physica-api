import os
import json
from typing import List, Optional
from groq import Groq
from pydantic import BaseModel
from .v2_models import StoryboardStep, NarrationStep

PROMPT_V2_NARRATOR = """
You are a master physics teacher, like Abdul Bari or from Khan Academy.
You are narrating a 3D video animation.
I will give you a sequence of visual storyboard steps.
For each step, I will provide the 'primitive_type' (what is shown on screen) and a 'physics_reason' (why it is shown).
You must write a teacher-style narration describing EXACTLY what is happening on screen in that step.
Keep your narration to 1-3 short, engaging sentences. Do not overexplain.
Output a JSON array of strings, where each string is the narration for the corresponding storyboard step in order.

JSON format expected:
{
  "narrations": ["Narration for step 1", "Narration for step 2", ...]
}
"""

class NarrationResponse(BaseModel):
    narrations: List[str]

class V2Narrator:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key required for V2 Narrator.")
        self.client = Groq(api_key=self.api_key)
        self.model = "llama-3.3-70b-versatile"

    def generate_narration(self, storyboard: List[StoryboardStep]) -> List[NarrationStep]:
        """Generates narration for each storyboard step."""
        
        # Prepare input
        input_data = [
            {
                "step": i,
                "primitive_type": step.primitive.primitive_type.value,
                "physics_reason": step.physics_reason
            }
            for i, step in enumerate(storyboard)
        ]
        
        prompt_text = json.dumps(input_data, indent=2)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": PROMPT_V2_NARRATOR},
                    {"role": "user", "content": prompt_text}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            content = response.choices[0].message.content
            parsed = NarrationResponse.model_validate_json(content)
            
            # Ensure lengths match
            if len(parsed.narrations) != len(storyboard):
                print(f"[V2Narrator] Warning: expected {len(storyboard)} narrations, got {len(parsed.narrations)}")
                # Fill missing with empty string
                while len(parsed.narrations) < len(storyboard):
                    parsed.narrations.append("")
                    
            return [NarrationStep(narration_text=text) for text in parsed.narrations[:len(storyboard)]]
            
        except Exception as e:
            print(f"[V2Narrator] Narration generation failed: {e}")
            # Fallback
            return [NarrationStep(narration_text=step.physics_reason) for step in storyboard]
