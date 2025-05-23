import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self, model: str = "gpt-4", temperature: float = 0.3, max_tokens: int = 1200):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise EnvironmentError("OPENAI_API_KEY not set in environment.")

        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        try:
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
        except Exception as e:
            print(f"❌ LLM call failed: {e}")
            return ""

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
