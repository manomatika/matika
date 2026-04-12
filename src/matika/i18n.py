import json
import os
from typing import Dict, Optional
from .core.paths import BASE_DIR, ROOT_DIR

class I18nService:
    """
    Localization Service for Matika.
    Handles loading of core and plugin-specific translations.
    """
    
    def __init__(self):
        # Instance-level cache
        self.translations_cache: Dict[str, Dict[str, str]] = {}

    def get_text(self, lang_code: str = "en") -> Dict[str, str]:
        """
        Detects the base language and returns the merged translation dict.
        """
        if not lang_code:
            lang_code = "en"
        
        # Simple extraction of primary language code (e.g., "en-US" -> "en")
        code = lang_code.split(",")[0].split("-")[0].strip().lower()
        
        text = self.load_language(code)
        
        # Fallback to English if the requested language is missing
        if text is None:
            text = self.load_language("en")
            
        return text if text is not None else {}

    def load_language(self, lang_code: str) -> Optional[Dict[str, str]]:
        """Loads core translations and all plugin overrides."""
        if lang_code in self.translations_cache:
            return self.translations_cache[lang_code]
        
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
                
                # Check for locales/lang.json in plugin package
                plugin_locale = os.path.join(plugin_path, "src", plugin_name, "locales", f"{lang_code}.json")
                if os.path.exists(plugin_locale):
                    try:
                        with open(plugin_locale, "r", encoding="utf-8") as f:
                            plugin_data = json.load(f)
                            combined_data.update(plugin_data)
                    except Exception:
                        pass
        
        self.translations_cache[lang_code] = combined_data
        return combined_data

# Legacy support for functional calls if needed, but instance-based is preferred
_global_i18n = I18nService()

def get_text(lang_code: str = "en") -> Dict[str, str]:
    return _global_i18n.get_text(lang_code)
