"""Anthropic (Claude) adapter for the vendor-neutral ``AIProvider`` interface.

Enabled by configuration alone:

    AI_PROVIDER=anthropic
    AI_API_KEY=<your Anthropic API key>
    AI_MODEL=claude-opus-5-5        # optional; this is the default

Nothing above this module knows which vendor is in use. The adapter only turns
already-computed facts into prose (``generate``) or into a JSON answer that
cites those facts (``generate_json``); the analyst validates whatever comes
back before showing it.

Notes on the request shape (Claude Opus 5.5):

* thinking is always on and cannot be disabled; depth is set with
  ``output_config.effort`` (its default is "medium" on this model, so it is
  set explicitly);
* ``max_tokens`` covers thinking as well as the answer, so it is generous --
  the prompt, not the token cap, keeps the answer short;
* a safety-classifier decline returns ``stop_reason == "refusal"``; the
  server-side fallback (``fallbacks: "default"``) re-runs a declined request on
  a suitable model inside the same call, and a refusal that survives it is
  reported as a provider error, never as an empty answer.
"""
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("ai_provider.anthropic")

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
EFFORT = "medium"
TIMEOUT_SECONDS = 120.0
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: Optional[str] = None, client=None):
        # Imported here so the application runs without the SDK installed
        # when no AI provider is configured.
        import anthropic

        self._anthropic = anthropic
        self.model = (model or DEFAULT_MODEL).strip()
        self.client = client or anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS)

    def is_configured(self) -> bool:
        return True

    # ------------------------------------------------------------------
    def _create(self, system_prompt: str, user_prompt: str,
                output_format: Optional[Dict[str, Any]] = None):
        from app.services.ai_provider import AIProviderError

        output_config: Dict[str, Any] = {"effort": EFFORT}
        if output_format:
            output_config["format"] = output_format
        a = self._anthropic
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                output_config=output_config,
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except a.AuthenticationError:
            raise AIProviderError("The AI provider rejected the API key (AI_API_KEY).")
        except a.PermissionDeniedError:
            raise AIProviderError("The AI provider key lacks permission for this model.")
        except a.NotFoundError:
            raise AIProviderError("The AI model '" + self.model + "' was not found (AI_MODEL).")
        except a.RateLimitError:
            raise AIProviderError("The AI provider is rate limiting requests. Try again shortly.")
        except a.BadRequestError as exc:
            raise AIProviderError("The AI provider rejected the request: "
                                  + str(getattr(exc, "message", "") or "bad request") + ".")
        except a.APIStatusError as exc:
            raise AIProviderError("The AI provider returned an error (HTTP "
                                  + str(exc.status_code) + ").")
        except a.APIConnectionError:
            raise AIProviderError("The AI provider could not be reached.")

        if response.stop_reason == "refusal":
            raise AIProviderError("The AI provider declined to answer this request.")
        if response.stop_reason == "max_tokens":
            raise AIProviderError("The AI provider's answer was cut off before it finished.")
        text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
        return text.strip()

    def generate(self, system_prompt: str, user_prompt: str,
                 max_tokens: int = 600) -> str:
        return self._create(system_prompt, user_prompt)

    def generate_json(self, system_prompt: str, user_prompt: str,
                      schema: Dict[str, Any]) -> Dict[str, Any]:
        """A JSON object conforming to ``schema`` (structured outputs)."""
        from app.services.ai_provider import AIProviderError

        text = self._create(system_prompt, user_prompt,
                            output_format={"type": "json_schema", "schema": schema})
        try:
            data = json.loads(text)
        except ValueError:
            raise AIProviderError("The AI provider returned an answer that was not valid JSON.")
        if not isinstance(data, dict):
            raise AIProviderError("The AI provider returned an unexpected answer shape.")
        return data


def factory(api_key: str, model: Optional[str] = None) -> AnthropicProvider:
    return AnthropicProvider(api_key=api_key, model=model)
