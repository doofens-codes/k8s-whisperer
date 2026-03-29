import os
from typing import Optional
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


class AIClient:
    """
    Groq-based LLM client.
    Maintains same interface as before for zero refactor in nodes.
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
            "GROQ_MODEL", "llama3-70b-8192"
        )

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        timeout: int = 60  # kept for compatibility, unused
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2  # low for deterministic infra reasoning
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise RuntimeError(f"Groq request failed: {e}")


# module-level instance
client = AIClient()