"""
Name Mapping Configuration
Maps technical service and model IDs to display-friendly names.
"""

from typing import Dict

# Model name mappings: technical_id -> friendly_display_name
# Shows actual model names in clean format without service-specific prefixes
MODEL_NAME_MAPPINGS: Dict[str, str] = {
    # Google Models
    "google/gemini-2.0-flash-001": "Gemini 2.0 Flash",
    "google/gemini-2.5-flash": "Gemini 2.5 Flash",
    "google/gemini-2.0-flash-thinking-001": "Gemini 2.0 Flash Thinking",
    "google/gemma-3-1b-it": "Gemma 3 1B",
    "google/gemma-2-9b-it": "Gemma 2 9B",
    # OpenAI Models
    "openai/gpt-5-chat": "GPT-5 Chat",
    "openai/gpt-4.1": "GPT-4.1",
    "openai/gpt-4o": "GPT-4o",
    "openai/gpt-4o-mini": "GPT-4o Mini",
    "openai/gpt-4o-search": "GPT-4o Search",
    "openai/gpt-4o-search-preview": "GPT-4o Search Preview",
    "openai/o1": "O1",
    "openai/o1-mini": "O1 Mini",
    "openai/o1-preview": "O1 Preview",
    # Anthropic Models
    "anthropic/claude-opus-4": "Claude Opus 4",
    "anthropic/claude-opus-4.5": "Claude Opus 4.5",
    "anthropic/claude-sonnet-4": "Claude Sonnet 4",
    "anthropic/claude-sonnet-4.5": "Claude Sonnet 4.5",
    "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet",
    "anthropic/claude-3-opus": "Claude 3 Opus",
    # DeepSeek Models
    "deepseek/deepseek-chat": "DeepSeek Chat",
    "deepseek/deepseek-chat-v3-0324": "DeepSeek Chat V3",
    "deepseek/deepseek-r1": "DeepSeek R1",
    "deepseek/deepseek-reasoner": "DeepSeek Reasoner",
    # xAI Models
    "x-ai/grok-2": "Grok 2",
    "x-ai/grok-beta": "Grok Beta",
    "x-ai/grok-4": "Grok 4",
    "x-ai/grok-4-beta": "Grok 4 Beta",
    # Meta Models
    "meta-llama/llama-3.1-405b-instruct": "Llama 3.1 405B",
    "meta-llama/llama-3.3-70b-instruct": "Llama 3.3 70B",
    "meta-llama/llama-4-maverick": "Llama 4 Maverick",
    # Mistral Models
    "mistralai/mistral-large": "Mistral Large",
    "mistralai/mistral-medium": "Mistral Medium",
    "mistralai/mistral-small": "Mistral Small",
    "mistralai/mixtral-8x7b": "Mixtral 8x7B",
    # Qwen Models
    "qwen/qwen-2.5-72b-instruct": "Qwen 2.5 72B",
    "qwen/qwq-32b-preview": "QwQ 32B Preview",
}

# Reverse mapping for converting friendly names back to technical IDs
FRIENDLY_TO_TECHNICAL: Dict[str, str] = {v: k for k, v in MODEL_NAME_MAPPINGS.items()}

# Platform name mappings
PLATFORM_MAPPINGS: Dict[str, str] = {
    "telegram": "public-platform",
    "internal": "private-platform",
}


def get_friendly_model_name(technical_name: str) -> str:
    """
    Convert technical model name to friendly display name.
    If no mapping exists, formats the model name cleanly.

    Args:
        technical_name: Technical model identifier (e.g., "google/gemini-2.0-flash-001")

    Returns:
        Friendly name (e.g., "Gemini 2.0 Flash")
    """
    if technical_name in MODEL_NAME_MAPPINGS:
        return MODEL_NAME_MAPPINGS[technical_name]

    # For unmapped models, create a clean display name
    if "/" in technical_name:
        _, model = technical_name.split("/", 1)
        # Clean up the model name: replace dashes/underscores with spaces, title case
        clean_name = model.replace("-", " ").replace("_", " ")
        # Remove common suffixes
        clean_name = clean_name.replace(" instruct", "").replace(" chat", "")
        # Title case
        words = clean_name.split()
        formatted_words = []
        for word in words:
            # Keep version numbers and special terms uppercase
            if word.replace(".", "").replace("v", "").isdigit() or word.upper() in [
                "GPT",
                "LLM",
                "AI",
            ]:
                formatted_words.append(word.upper())
            else:
                formatted_words.append(word.capitalize())
        return " ".join(formatted_words)

    return technical_name


def get_technical_model_name(friendly_name: str) -> str:
    """
    Convert friendly model name back to technical name.

    Args:
        friendly_name: Friendly model identifier (e.g., "Gemini 2.0 Flash")

    Returns:
        Technical name (e.g., "google/gemini-2.0-flash-001")
        Returns input if no mapping exists.
    """
    return FRIENDLY_TO_TECHNICAL.get(friendly_name, friendly_name)


def get_friendly_platform_name(technical_name: str) -> str:
    """
    Convert platform name to friendly name.

    Args:
        technical_name: Technical platform name (e.g., "telegram")

    Returns:
        Friendly platform name (e.g., "public-platform")
    """
    return PLATFORM_MAPPINGS.get(technical_name, "unknown-platform")


def mask_session_id(session_id: str, show_chars: int = 8) -> str:
    """
    Mask session ID for logging, showing only first N characters.

    Args:
        session_id: Full session ID
        show_chars: Number of characters to show (default: 8)

    Returns:
        Masked session ID (e.g., "a1b2c3d4...")
    """
    if len(session_id) <= show_chars:
        return session_id
    return f"{session_id[:show_chars]}..."
