"""AI provider abstraction.

The application is deliberately not built around any one vendor. Everything
above this module talks to the ``AIProvider`` interface, so a provider is added
later through configuration and a small adapter, without touching the analyst.

No vendor SDK is shipped here on purpose: adding an unused dependency and a
half-configured client would be worse than an explicit "not configured" state.
``NotConfiguredProvider`` is the default, and it fails loudly rather than
returning something that looks like analysis.
"""
import logging
from typing import Optional, Protocol, runtime_checkable

from app.config import settings

logger = logging.getLogger("ai_provider")


class AIProviderError(Exception):
    """The provider was reachable but could not produce a result."""


class AIProviderNotConfigured(AIProviderError):
    """No provider is configured. Not an error condition -- a state."""


@runtime_checkable
class AIProvider(Protocol):
    """What the analyst needs from any provider.

    ``generate`` returns prose only. It is never asked to produce facts,
    figures or structure: those are computed before it is called, and its
    output is validated afterwards.
    """

    name: str

    def is_configured(self) -> bool:
        ...

    def generate(self, system_prompt: str, user_prompt: str,
                 max_tokens: int = 600) -> str:
        ...


class NotConfiguredProvider:
    """The default. Reports its state and refuses to invent one."""

    name = "not_configured"

    def is_configured(self) -> bool:
        return False

    def generate(self, system_prompt: str, user_prompt: str,
                 max_tokens: int = 600) -> str:
        raise AIProviderNotConfigured(
            "No AI provider is configured. Set AI_PROVIDER and AI_API_KEY to "
            "enable narrative summaries. Factual analysis does not require one.")


#: Adapters register here so a provider can be enabled by configuration alone.
#: Empty by design until a vendor adapter is added.
PROVIDER_REGISTRY = {}


def register_provider(name: str, factory) -> None:
    """Register a provider factory under a configuration name."""
    PROVIDER_REGISTRY[name.strip().lower()] = factory


def get_ai_provider(provider_name: Optional[str] = None,
                    api_key: Optional[str] = None) -> AIProvider:
    """The configured provider, or ``NotConfiguredProvider``.

    Never raises: a missing provider is a state the caller reports, not a
    failure that should take an endpoint down.
    """
    name = (provider_name or getattr(settings, "AI_PROVIDER", "") or "").strip().lower()
    key = api_key or getattr(settings, "AI_API_KEY", None)

    if not name or not key:
        return NotConfiguredProvider()

    factory = PROVIDER_REGISTRY.get(name)
    if factory is None:
        logger.warning("AI_PROVIDER=%r is not registered; no adapter is installed.", name)
        return NotConfiguredProvider()

    try:
        return factory(api_key=key, model=getattr(settings, "AI_MODEL", None))
    except Exception as exc:  # pragma: no cover - depends on a future adapter
        logger.warning("AI provider %r failed to initialise: %s", name, type(exc).__name__)
        return NotConfiguredProvider()
