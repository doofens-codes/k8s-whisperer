import os
from typing import Optional
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


class AIClient:
    """
    Groq-based LLM client.
    Supports system prompts for proper role-based reasoning.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY not set")

        self.client = Groq(api_key=self.api_key)
        self.default_model = default_model or os.getenv(
            "GROQ_MODEL", "llama-3.1-8b-instant"
        )

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        timeout: int = 60  # kept for compatibility
    ) -> str:
        messages = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            raise RuntimeError(f"Groq request failed: {e}")


# module-level instance
client = AIClient()