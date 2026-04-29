import os
import json
import logging
from typing import Dict, List, Any, Optional

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
    Standalone service for discovering and loading menu files.

    Scans two locations:
      - core_menus_dir: framework-owned menus (src/matika/menus/)
      - plugins_dir:    one subdirectory per AppLug

    load_all() loads legacy *_menu.json files (core menus only in practice).
    load_applug_menus() loads the consolidated *_menus.json files from plugin
    directories, returning structured application and per-role menu data.
    """

    def __init__(self, core_menus_dir: str, plugins_dir: str):
        self.core_menus_dir = core_menus_dir
        self.plugins_dir = plugins_dir
        self._cache: Optional[Dict[str, List[Dict]]] = None
        self._applug_cache: Optional[Dict[str, Dict]] = None

    # ------------------------------------------------------------------
    # Core menu loading (legacy *_menu.json — used for core menus only)
    # ------------------------------------------------------------------

    def load_all(self) -> Dict[str, List[Dict]]:
        """
        Returns {source_id: [menu_dict, ...]} for every discovered *_menu.json.
        Result is cached after the first call; call invalidate_cache() to refresh.
        """
        if self._cache is None:
            self._cache = self._do_load()
        return self._cache

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

    # ------------------------------------------------------------------
    # Consolidated applug menu loading (*_menus.json)
    # ------------------------------------------------------------------

    def load_applug_menus(self) -> Dict[str, Dict]:
        """
        Scans plugin directories for *_menus.json files and returns structured data.

        Returns:
            {
                plugin_id: {
                    "application": <menu dict or None>,
                    "roles": { role_name: <role entry dict>, ... }
                }
            }

        Emits a loud WARNING if a plugin directory contains a *_permission.json
        file but no *_menus.json — its pages would be unreachable from any menu.

        Result is cached after the first call; call invalidate_cache() to refresh.
        """
        if self._applug_cache is None:
            self._applug_cache = self._do_load_applug_menus()
        return self._applug_cache

    def _do_load_applug_menus(self) -> Dict[str, Dict]:
        result: Dict[str, Dict] = {}
        if not os.path.exists(self.plugins_dir):
            return result

        for entry in sorted(os.listdir(self.plugins_dir)):
            plugin_path = os.path.join(self.plugins_dir, entry)
            if not os.path.isdir(plugin_path):
                continue

            menus_file: Optional[str] = None
            permission_file: Optional[str] = None
            for filename in os.listdir(plugin_path):
                if filename.endswith("_menus.json"):
                    menus_file = os.path.join(plugin_path, filename)
                if filename.endswith("_permission.json") or filename.endswith("_permissions.json"):
                    permission_file = os.path.join(plugin_path, filename)

            if permission_file and not menus_file:
                logger.warning(
                    "WARNING: AppLug '%s' declares permissions but provides no "
                    "*_menus.json. Its pages will be unreachable from any menu. "
                    "This is likely a development oversight.",
                    entry,
                )

            if not menus_file:
                continue

            try:
                with open(menus_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                schema = data.get("schema_version")
                if schema != SUPPORTED_SCHEMA:
                    logger.warning(
                        "Skipping %s: unsupported schema_version '%s'", menus_file, schema
                    )
                    continue

                menus_section = data.get("menus", {})
                application = menus_section.get("application") or None

                roles_dict: Dict[str, Dict] = {}
                for role_entry in menus_section.get("roles", []):
                    role_name = role_entry.get("role")
                    if role_name:
                        roles_dict[role_name] = role_entry

                result[entry] = {"application": application, "roles": roles_dict}

            except Exception as exc:
                logger.error("Failed to load applug menus file %s: %s", menus_file, exc)

        return result

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def invalidate_cache(self) -> None:
        self._cache = None
        self._applug_cache = None
