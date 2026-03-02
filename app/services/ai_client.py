import logging
import httpx
import anthropic
import openai
from app.database import get_all_settings

logger = logging.getLogger("medical")


def _get_settings() -> dict[str, str]:
    return get_all_settings()


def get_current_provider() -> str:
    """Return the currently configured provider name."""
    return _get_settings().get("ai_provider", "claude")


async def get_ai_response(system: str, user_message: str, max_tokens: int = 1024) -> str:
    """Unified AI response function. Reads provider config from DB on every call (hot-reload)."""
    settings = _get_settings()
    provider = settings.get("ai_provider", "claude")

    if provider == "claude":
        return await _call_claude(settings, system, user_message, max_tokens)
    elif provider == "openai":
        return await _call_openai(settings, system, user_message, max_tokens)
    elif provider == "ollama":
        return await _call_ollama(settings, system, user_message, max_tokens)
    else:
        raise ValueError(f"Unknown AI provider: {provider}")


async def _call_claude(settings: dict, system: str, user_message: str, max_tokens: int) -> str:
    api_key = settings.get("claude_api_key", "")
    model = settings.get("claude_model", "claude-sonnet-4-20250514")
    if not api_key:
        raise ValueError("Claude API key not configured")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text.strip()


async def _call_openai(settings: dict, system: str, user_message: str, max_tokens: int) -> str:
    api_key = settings.get("openai_api_key", "")
    model = settings.get("openai_model", "gpt-4o")
    if not api_key:
        raise ValueError("OpenAI API key not configured")

    client = openai.AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content.strip()


async def _call_ollama(settings: dict, system: str, user_message: str, max_tokens: int) -> str:
    base_url = settings.get("ollama_base_url", "http://localhost:11434")
    model = settings.get("ollama_model", "llama3")

    client = openai.AsyncOpenAI(
        base_url=f"{base_url.rstrip('/')}/v1",
        api_key="ollama",
        timeout=httpx.Timeout(None),  # No timeout for local Ollama
    )
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content.strip()


async def validate_provider(provider: str, settings: dict) -> dict:
    """Test connection to the specified provider. Returns {ok: bool, error: str|None}."""
    try:
        if provider == "claude":
            api_key = settings.get("claude_api_key", "")
            model = settings.get("claude_model", "claude-sonnet-4-20250514")
            if not api_key:
                return {"ok": False, "error": "API key is empty"}
            client = anthropic.AsyncAnthropic(api_key=api_key)
            await client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return {"ok": True, "error": None}

        elif provider == "openai":
            api_key = settings.get("openai_api_key", "")
            model = settings.get("openai_model", "gpt-4o")
            if not api_key:
                return {"ok": False, "error": "API key is empty"}
            client = openai.AsyncOpenAI(api_key=api_key)
            await client.chat.completions.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return {"ok": True, "error": None}

        elif provider == "ollama":
            base_url = settings.get("ollama_base_url", "http://localhost:11434")
            model = settings.get("ollama_model", "llama3")
            client = openai.AsyncOpenAI(
                base_url=f"{base_url.rstrip('/')}/v1",
                api_key="ollama",
                timeout=httpx.Timeout(None),
            )
            await client.chat.completions.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return {"ok": True, "error": None}

        else:
            return {"ok": False, "error": f"Unknown provider: {provider}"}

    except Exception as e:
        logger.error(f"Provider validation failed for {provider}: {e}")
        return {"ok": False, "error": str(e)}
