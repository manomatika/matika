import json
import os

from .core.paths import BASE_DIR

# Module-level cache for translations: { "en": {...}, "es": {...} }
TRANSLATIONS_CACHE = {}

def load_language(lang_code: str):
    """Loads a specific language file from the locales directory."""
    if lang_code in TRANSLATIONS_CACHE:
        return TRANSLATIONS_CACHE[lang_code]
    
    path = os.path.join(BASE_DIR, "src", "matika", "locales", f"{lang_code}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            TRANSLATIONS_CACHE[lang_code] = data
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        # If the requested language isn't found, we'll need to fallback to English
        return None

def get_text(lang_code="en"):
    """
    Detects the base language from the lang_code (usually Accept-Language header).
    Loads the corresponding JSON file and falls back to English if missing.
    """
    # Normalize header (e.g., 'en-US,en;q=0.9' -> 'en')
    base_lang = lang_code.split(",")[0].split("-")[0].lower() if lang_code else "en"
    
    # Try to load the requested language
    text = load_language(base_lang)
    
    # Fallback to English if the requested language is missing or failed
    if text is None:
        text = load_language("en")
        
    # Final safety fallback to an empty dict if even English is missing
    return text if text is not None else {}
