import os
from openai import OpenAI
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self, model: str = "claude-sonnet-4-20250514", temperature: float = 0.3, max_tokens: int = 8000):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Determine provider based on model name
        if self._is_claude_model(model):
            self.provider = "anthropic"
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise EnvironmentError("ANTHROPIC_API_KEY not set in environment.")
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.provider = "openai"
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise EnvironmentError("OPENAI_API_KEY not set in environment.")
            self.client = OpenAI(api_key=self.api_key)

    def _is_claude_model(self, model: str) -> bool:
        """Check if the model is a Claude model"""
        return model.lower().startswith("claude")

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        try:
            if self.provider == "anthropic":
                return self._chat_anthropic(system_prompt, user_prompt)
            else:
                return self._chat_openai(system_prompt, user_prompt)
        except Exception as e:
            print(f"❌ LLM call failed ({self.provider}/{self.model}): {e}")
            return ""

    def _chat_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        """Handle Anthropic/Claude API calls"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.content[0].text.strip()

    def _chat_openai(self, system_prompt: str, user_prompt: str) -> str:
        """Handle OpenAI API calls"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    def get_available_models():
        """Return a dictionary of available models by provider"""
        return {
            "openai": [
                "gpt-4-turbo",
                "gpt-4",
                "gpt-3.5-turbo"
            ],
            "claude": [
                "claude-sonnet-4-20250514",  # Latest Claude Sonnet 4
                "claude-3-5-sonnet-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ]
        }

# ---------------------------
# Quick Test (run directly)
# ---------------------------
if __name__ == "__main__":
    llm = LLMClient()
    response = llm.chat(
        "You are a helpful assistant.",
        "What is the Pythagorean Theorem?"
    )
    print("\n✅ Test Response:\n", response or "No output returned.")