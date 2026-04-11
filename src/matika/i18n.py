import json
import os

from .core.paths import BASE_DIR, ROOT_DIR

# Module-level cache for translations: { "en": {...}, "es": {...} }
TRANSLATIONS_CACHE = {}

def load_language(lang_code: str):
    """Loads a specific language file and any plugin overrides."""
    if lang_code in TRANSLATIONS_CACHE:
        return TRANSLATIONS_CACHE[lang_code]
    
    # 1. Load Core Matika Translations
    path = os.path.join(BASE_DIR, "src", "matika", "locales", f"{lang_code}.json")
    combined_data = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            combined_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    # 2. Scan Plugins for Localization Overrides
    plugins_dir = os.path.join(ROOT_DIR, "plugins")
    if os.path.exists(plugins_dir):
        for plugin_name in os.listdir(plugins_dir):
            plugin_path = os.path.join(plugins_dir, plugin_name)
            if not os.path.isdir(plugin_path):
                continue
            
            # Check for locales/lang.json in plugin
            plugin_locale = os.path.join(plugin_path, "src", plugin_name, "locales", f"{lang_code}.json")
            if os.path.exists(plugin_locale):
                try:
                    with open(plugin_locale, "r", encoding="utf-8") as f:
                        plugin_data = json.load(f)
                        combined_data.update(plugin_data)
                except Exception:
                    pass
    
    TRANSLATIONS_CACHE[lang_code] = combined_data
    return combined_data

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
