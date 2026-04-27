import os
import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

SUPPORTED_SCHEMA = "1.0"


def menu_is_visible(menu: Dict[str, Any], user_roles: List[str]) -> bool:
    """A menu with no roles field is visible to all; otherwise user must hold at least one listed role."""
    required = menu.get("roles", [])
    return not required or any(r in user_roles for r in required)


def filter_items(items: List[Dict], user_roles: List[str]) -> List[Dict]:
    """
    Recursively filters menu items by user roles.
    Items with no roles field are visible to all authenticated users.
    Menu-type items with no visible children are dropped entirely.
    Separators are cleaned so none appear at the edges or consecutively.
    """
    result: List[Dict] = []
    for item in items:
        item_type = item.get("type")
        if item_type == "Separator":
            result.append(item)
            continue
        required = item.get("roles", [])
        if required and not any(r in user_roles for r in required):
            continue
        if item_type == "Menu":
            children = filter_items(item.get("items", []), user_roles)
            if children:
                result.append({**item, "items": children})
        else:
            result.append(item)
    return clean_separators(result)


def clean_separators(items: List[Dict]) -> List[Dict]:
    """Remove leading, trailing, and consecutive Separator items."""
    result: List[Dict] = []
    for item in items:
        if item.get("type") == "Separator":
            if result and result[-1].get("type") != "Separator":
                result.append(item)
        else:
            result.append(item)
    if result and result[-1].get("type") == "Separator":
        result.pop()
    return result


def translate_items(items: List[Dict], t: Dict[str, str]) -> List[Dict]:
    """
    Recursively translates label_key → label on each item.
    The roles field is intentionally omitted from output — role filtering
    is applied server-side before this function is called.
    """
    result: List[Dict] = []
    for item in items:
        item_type = item.get("type")
        if item_type == "Separator":
            result.append({"type": "Separator"})
            continue
        translated: Dict[str, Any] = {"type": item_type}
        if "label_key" in item:
            translated["label"] = t.get(item["label_key"], item["label_key"])
        if "href" in item:
            translated["href"] = item["href"]
        if item.get("open_new_tab"):
            translated["open_new_tab"] = True
        if "items" in item:
            translated["items"] = translate_items(item["items"], t)
        result.append(translated)
    return result


class MenuLoaderService:
    """
    Standalone service for discovering and loading *_menu.json files.

    Scans two locations:
      - core_menus_dir: framework-owned menus (src/matika/menus/)
      - plugins_dir:    one subdirectory per AppLug, each containing *_menu.json files

    Returns raw (unfiltered, untranslated) menu objects grouped by source key.
    'core' is the reserved source key for framework menus; plugin source keys
    are the plugin directory names (which must match the plugin id in applug.json).
    """

    def __init__(self, core_menus_dir: str, plugins_dir: str):
        self.core_menus_dir = core_menus_dir
        self.plugins_dir = plugins_dir
        self._cache: Optional[Dict[str, List[Dict]]] = None

    def load_all(self) -> Dict[str, List[Dict]]:
        """
        Returns {source_id: [menu_dict, ...]} for every discovered *_menu.json.
        Result is cached after the first call; call invalidate_cache() to refresh.
        """
        if self._cache is None:
            self._cache = self._do_load()
        return self._cache

    def invalidate_cache(self) -> None:
        self._cache = None

    def _do_load(self) -> Dict[str, List[Dict]]:
        result: Dict[str, List[Dict]] = {}

        core = self._load_from_dir(self.core_menus_dir)
        if core:
            result["core"] = core

        if os.path.exists(self.plugins_dir):
            for entry in sorted(os.listdir(self.plugins_dir)):
                plugin_path = os.path.join(self.plugins_dir, entry)
                if not os.path.isdir(plugin_path):
                    continue
                plugin_menus = self._load_from_dir(plugin_path)
                if plugin_menus:
                    result[entry] = plugin_menus

        return result

    def _load_from_dir(self, directory: str) -> List[Dict]:
        """Scans a single directory for *_menu.json files and returns all menu objects found."""
        menus: List[Dict] = []
        if not os.path.exists(directory):
            return menus
        for filename in sorted(os.listdir(directory)):
            if not filename.endswith("_menu.json"):
                continue
            path = os.path.join(directory, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                schema = data.get("schema_version")
                if schema != SUPPORTED_SCHEMA:
                    logger.warning(
                        "Skipping %s: unsupported schema_version '%s'", path, schema
                    )
                    continue
                menus.extend(data.get("menus", []))
            except Exception as exc:
                logger.error("Failed to load menu file %s: %s", path, exc)
        return menus
