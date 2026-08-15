from google import genai
from google.genai import types

import config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _model_chain():
    chain = [config.GEMINI_MODEL]
    if config.GEMINI_FALLBACK_MODEL and config.GEMINI_FALLBACK_MODEL != config.GEMINI_MODEL:
        chain.append(config.GEMINI_FALLBACK_MODEL)
    return chain


def _generate_text(model, system, user, schema_model, temperature):
    client = _get_client()
    cfg = {
        "system_instruction": system,
        "temperature": temperature,
        "thinking_config": types.ThinkingConfig(thinking_level="MINIMAL"),
    }
    if schema_model is not None:
        cfg["response_mime_type"] = "application/json"
        cfg["response_schema"] = schema_model
    response = client.models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(**cfg),
    )
    if not response.text:
        raise ValueError("LLM returned empty content")
    return response.text


def generate_with_fallback(system, user, schema_model=None, temperature=0.7):
    errors = []
    for model in _model_chain():
        try:
            return _generate_text(model, system, user, schema_model, temperature), model
        except Exception as e:
            errors.append(f"{model}: {e}")
            print(f"⚠️ LLM {model} failed: {e}")
    raise RuntimeError("LLM unavailable: " + " | ".join(errors))
