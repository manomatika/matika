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

    load_menus() returns a unified structure for both core and plugin menus.
    Each source maps to a dict with optional keys: application, roles, system.
      - application: single menu dict (or None)
      - roles:       {role_name: role_entry_dict} (or {})
      - system:      single menu dict (or None)

    Core menus are assembled by merging all *_menus.json files found in
    core_menus_dir. Plugin menus expect exactly one *_menus.json per plugin
    directory.
    """

    def __init__(self, core_menus_dir: str, plugins_dir: str):
        self.core_menus_dir = core_menus_dir
        self.plugins_dir = plugins_dir
        self._cache: Optional[Dict[str, Dict]] = None

    def load_menus(self) -> Dict[str, Dict]:
        """
        Returns {source_id: {"application": …, "roles": {…}, "system": …}} for
        all discovered *_menus.json files.
        "core" is assembled by merging all *_menus.json files in core_menus_dir.
        Each plugin contributes one entry keyed by its directory name.
        Result is cached after the first call; call invalidate_cache() to refresh.
        """
        if self._cache is None:
            self._cache = self._do_load_menus()
        return self._cache

    def _do_load_menus(self) -> Dict[str, Dict]:
        result: Dict[str, Dict] = {}

        # Core menus: merge all *_menus.json files in core_menus_dir.
        core = self._load_core_menus()
        if core:
            result["core"] = core

        # Plugin menus: one *_menus.json per plugin subdirectory.
        if os.path.exists(self.plugins_dir):
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

                parsed = self._parse_menus_file(menus_file)
                if parsed is not None:
                    result[entry] = parsed

        return result

    def _load_core_menus(self) -> Optional[Dict]:
        """Merge all *_menus.json files in core_menus_dir into a single dict."""
        if not os.path.exists(self.core_menus_dir):
            return None

        merged_roles: Dict[str, Dict] = {}
        merged_application: Optional[Dict] = None
        merged_system: Optional[Dict] = None
        found_any = False

        for filename in sorted(os.listdir(self.core_menus_dir)):
            if not filename.endswith("_menus.json"):
                continue
            path = os.path.join(self.core_menus_dir, filename)
            parsed = self._parse_menus_file(path)
            if parsed is None:
                continue
            found_any = True
            for role_name, role_entry in parsed.get("roles", {}).items():
                merged_roles[role_name] = role_entry
            if parsed.get("application") is not None:
                merged_application = parsed["application"]
            if parsed.get("system") is not None:
                merged_system = parsed["system"]

        if not found_any:
            return None

        return {
            "application": merged_application,
            "roles": merged_roles,
            "system": merged_system,
        }

    def _parse_menus_file(self, path: str) -> Optional[Dict]:
        """
        Read and validate a single *_menus.json file.
        Returns {"application": …, "roles": {role_name: entry}, "system": …}
        or None on schema mismatch or parse error.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            schema = data.get("schema_version")
            if schema != SUPPORTED_SCHEMA:
                logger.warning(
                    "Skipping %s: unsupported schema_version '%s'", path, schema
                )
                return None

            menus_section = data.get("menus", {})
            application = menus_section.get("application") or None
            system = menus_section.get("system") or None

            roles_dict: Dict[str, Dict] = {}
            for role_entry in menus_section.get("roles", []):
                role_name = role_entry.get("role")
                if role_name:
                    roles_dict[role_name] = role_entry

            return {"application": application, "roles": roles_dict, "system": system}

        except Exception as exc:
            logger.error("Failed to load menus file %s: %s", path, exc)
            return None

    def invalidate_cache(self) -> None:
        self._cache = None
