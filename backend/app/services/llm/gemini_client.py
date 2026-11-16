"""Gemini API client (google-genai SDK).

Notes:
- The model name comes from GEMINI_MODEL in .env, so it can change without code edits.
- From Gemini 3.6 Flash onward Google deprecated temperature/top_p/top_k, so they are not sent.
- Transient errors (429 rate limit, 500/503) are retried with exponential backoff.
"""
import asyncio
import logging

from app.core.exceptions import ExternalServiceError, ServiceNotConfiguredError

logger = logging.getLogger(__name__)

_RETRYABLE = {429, 500, 503}


class GeminiClient:
    def __init__(self, api_key: str | None, model: str, max_output_tokens: int = 600, thinking_level: str | None = None):
        self.api_key = api_key
        self.thinking_level = thinking_level or None
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if not self.api_key:
            raise ServiceNotConfiguredError("Gemini API key is not set. Add GEMINI_API_KEY to backend/.env")
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_instruction: str,
        retries: int = 3,
        image: tuple[bytes, str] | None = None,
        json_output: bool = False,
        max_output_tokens: int | None = None,
    ) -> str:
        """`image` = (bytes, mime type) to send a photo with the prompt; `json_output` asks for JSON only."""
        from google.genai import errors, types

        client = self._get_client()
        contents = [types.Part.from_bytes(data=image[0], mime_type=image[1]), prompt] if image else prompt

        def make_config(with_thinking: bool):
            extra = {}
            if with_thinking and self.thinking_level:
                extra["thinking_config"] = types.ThinkingConfig(thinking_level=self.thinking_level)
            return types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=max_output_tokens or self.max_output_tokens,
                # no tools are used, so turn off automatic function calling
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                **({"response_mime_type": "application/json"} if json_output else {}),
                **extra,
            )

        config = make_config(with_thinking=True)
        delay = 1.5
        for attempt in range(1, retries + 1):
            try:
                response = await client.aio.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
                text = (response.text or "").strip()
                if not text:
                    raise ExternalServiceError("Gemini returned an empty answer (it may have been blocked by safety filters)")
                return text
            except errors.APIError as exc:
                code = getattr(exc, "code", None)
                if code == 400 and self.thinking_level and "thinking" in str(exc).lower():
                    # this model does not accept the thinking setting: use its default and continue
                    logger.warning("Model %s rejected thinking_level=%s; using its default", self.model, self.thinking_level)
                    self.thinking_level = None
                    config = make_config(with_thinking=False)
                    continue
                logger.warning("Gemini error (attempt %s/%s): %s %s", attempt, retries, code, exc)
                if code in _RETRYABLE and attempt < retries:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                if code in (401, 403):
                    raise ExternalServiceError("Gemini rejected the API key. Check GEMINI_API_KEY.") from exc
                if code == 404:
                    raise ExternalServiceError(f"Gemini model '{self.model}' was not found. Check GEMINI_MODEL.") from exc
                if code == 429:
                    raise ExternalServiceError("Gemini rate limit reached. Please wait a minute and try again.") from exc
                raise ExternalServiceError("The AI service is unavailable right now. Please try again.") from exc
        raise ExternalServiceError("The AI service is unavailable right now. Please try again.")
