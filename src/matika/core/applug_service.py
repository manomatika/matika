import os
import json
import logging
import importlib
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from .paths import ROOT_DIR, BASE_DIR
from .applug import BaseAppLug
from .menu_loader import MenuLoaderService, menu_is_visible, filter_items, translate_items
from ..models import Role, Permission
from .constants import PageType, PermissionLevel

logger = logging.getLogger(__name__)


class AppLugService:
    """
    Discovery and Registration Engine for Matika AppLugs.
    Scans ~/Matika/plugins/ for applug.json manifests.
    """

    def __init__(
        self,
        plugins_dir: Optional[str] = None,
        templates: Optional[Any] = None,
        app: Optional[Any] = None,
    ):
        if plugins_dir is not None:
            self.plugins_dir = plugins_dir
        else:
            # MATIKA_PLUGINS_DIR lets the test suite supply an isolated temp
            # directory without touching the project's plugins/ folder.
            self.plugins_dir = (
                os.environ.get("MATIKA_PLUGINS_DIR")
                or os.path.join(ROOT_DIR, "plugins")
            )

        self.templates = templates
        self.app = app
        self.loaded_plugins: Dict[str, BaseAppLug] = {}

        os.makedirs(self.plugins_dir, exist_ok=True)

        core_menus_dir = os.path.join(BASE_DIR, "src", "matika", "menus")
        self.menu_loader = MenuLoaderService(
            core_menus_dir=core_menus_dir,
            plugins_dir=self.plugins_dir,
        )

    # ------------------------------------------------------------------
    # Plugin discovery
    # ------------------------------------------------------------------

    def discover(self, db: Session) -> List[BaseAppLug]:
        """
        Scans for plugins and attempts to load them.
        """
        from .paths import ROOT_DIR
        actual_plugins_dir = self.plugins_dir if self.plugins_dir else os.path.join(ROOT_DIR, "plugins")

        print(f"DEBUG: AppLugService.discover scanning {actual_plugins_dir}")
        logger.info(f"Scanning for plugins in {actual_plugins_dir}...")

        if not os.path.exists(actual_plugins_dir):
            print(f"DEBUG: plugins_dir does NOT exist: {actual_plugins_dir}")
            return []

        print(f"DEBUG: plugins_dir exists. Contents: {os.listdir(actual_plugins_dir)}")

        for plugin_name in os.listdir(actual_plugins_dir):
            plugin_path = os.path.join(actual_plugins_dir, plugin_name)
            print(f"DEBUG: Checking entry: {plugin_name} at {plugin_path}")

            if not os.path.isdir(plugin_path):
                print(f"DEBUG: {plugin_name} is not a directory.")
                continue

            manifest_file = os.path.join(plugin_path, "applug.json")
            if not os.path.exists(manifest_file):
                print(f"DEBUG: {manifest_file} does not exist.")
                continue

            print(f"DEBUG: Found manifest at {manifest_file}")
            try:
                with open(manifest_file, "r") as f:
                    manifest = json.load(f)

                plugin_id = manifest.get("id")
                print(f"DEBUG: Processing plugin {plugin_id}")

                entry_point = manifest.get("entry_point")
                print(f"DEBUG: entry_point={entry_point}")
                if not entry_point:
                    logger.error(f"Plugin {plugin_name} is missing 'entry_point' in manifest.")
                    continue

                module_path, class_name = entry_point.rsplit(".", 1)
                print(f"DEBUG: module_path={module_path}, class_name={class_name}")

                import sys
                plugin_src_path = os.path.join(plugin_path, "src")
                if os.path.exists(plugin_src_path) and plugin_src_path not in sys.path:
                    print(f"DEBUG: adding {plugin_src_path} to sys.path")
                    sys.path.insert(0, plugin_src_path)
                elif plugin_path not in sys.path:
                    print(f"DEBUG: adding {plugin_path} to sys.path")
                    sys.path.insert(0, plugin_path)

                project_src = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                if project_src not in sys.path:
                    sys.path.insert(0, project_src)

                module = importlib.import_module(module_path)
                print(f"DEBUG: module loaded: {module}")

                plugin_class = getattr(module, class_name)
                print(f"DEBUG: plugin_class: {plugin_class}")

                plugin_instance = plugin_class(manifest)
                plugin_instance.templates = self.templates
                plugin_instance.app = self.app
                self.loaded_plugins[plugin_instance.id] = plugin_instance

                self._register_plugin_entities(plugin_instance, db)
                plugin_instance.on_load(db)

                if self.app:
                    self.app.include_router(plugin_instance.get_router())

                logger.info(f"Successfully loaded plugin: [PLUGIN:{plugin_instance.id}] v{plugin_instance.version}")

            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_name}: {e}")
                import traceback
                logger.error(traceback.format_exc())

        return list(self.loaded_plugins.values())

    def _register_plugin_entities(self, plugin: BaseAppLug, db: Session):
        """Auto-provisions Roles and Permissions defined in the manifest."""
        logger.info(f"[PLUGIN:{plugin.id}] Registering manifest entities...")

        perms = plugin.manifest.get("permissions", [])
        for p in perms:
            path = p.get("page_path")
            ptype = p.get("page_type", "Maintenance")
            roles_map = p.get("roles", {})

            for role_name, level_name in roles_map.items():
                role = db.query(Role).filter(Role.name == role_name).first()
                if not role:
                    role = Role(
                        name=role_name,
                        description=f"Auto-created for plugin {plugin.id}",
                        is_system=False,
                    )
                    db.add(role)
                    db.flush()

                level = getattr(PermissionLevel, level_name.upper(), PermissionLevel.NONE)
                existing_perm = db.query(Permission).filter(
                    Permission.page_path == path,
                    Permission.role_id == role.id,
                ).first()

                if not existing_perm:
                    db.add(Permission(
                        page_path=path,
                        page_type=getattr(PageType, ptype.upper(), PageType.MAINTENANCE),
                        role_id=role.id,
                        level=level,
                        is_system=True,
                    ))
                else:
                    if existing_perm.level != level:
                        existing_perm.level = level

        db.commit()

    # ------------------------------------------------------------------
    # Menu hub context
    # ------------------------------------------------------------------

    def get_menus_for_context(
        self, user_roles: List[str], t: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Builds the full menu hub structure for template injection.

        Applies server-side role filtering (non-admin users never receive
        admin URLs) and pre-translates all label_key fields.

        Returns:
            {
                "selector": [ {id, label, type}, ... ],
                "hubs":     { hub_id: [ menu_item, ... ], ... }
            }
        """
        raw = self.menu_loader.load_all()

        # ------ filter & translate -------
        # filtered[source] = role-filtered raw menu dicts (for role analysis)
        # translated[source] = client-ready translated menu dicts
        filtered: Dict[str, List[Dict]] = {}
        translated: Dict[str, List[Dict]] = {}

        for source, menus in raw.items():
            # Skip menu files for plugins that failed to load.
            if source != "core" and source not in self.loaded_plugins:
                logger.warning(
                    "Menu files found for unloaded plugin '%s' — skipping.", source
                )
                continue

            f_list: List[Dict] = []
            t_list: List[Dict] = []
            for menu in menus:
                if not menu_is_visible(menu, user_roles):
                    continue
                filtered_items = filter_items(menu.get("items", []), user_roles)
                if not filtered_items:
                    # All items were role-filtered away; hide the menu entirely.
                    continue
                f_list.append({**menu, "items": filtered_items})
                t_list.append({
                    "id": menu["id"],
                    "label": t.get(menu["label_key"], menu["label_key"]),
                    "type": "Menu",   # Hub rendering type; menu category is for selector only
                    "items": translate_items(filtered_items, t),
                })
            if f_list:
                filtered[source] = f_list
                translated[source] = t_list

        # ------ selector ------
        # Built as a structured list with type discriminants understood by the client:
        #   "item"      — selectable entry that activates a hub
        #   "separator" — visual horizontal rule
        #   "header"    — non-selectable section label (grey text)
        selector: List[Dict] = [
            {"type": "item", "id": "__default__", "label": t.get("menu_type_default", "Default")},
            {"type": "separator"},
            {"type": "item", "id": "__favorites__", "label": t.get("menu_type_favorites", "Favorites")},
        ]

        # Applications section — only when at least one plugin has visible menus.
        app_entries: List[Dict] = []
        for plugin_id, plugin in self.loaded_plugins.items():
            if plugin_id in translated:
                label = (
                    plugin.manifest.get("display_name")
                    or plugin.manifest.get("name", plugin_id)
                )
                app_entries.append({"type": "item", "id": plugin_id, "label": label})

        if app_entries:
            selector.append({"type": "separator"})
            selector.append({"type": "header", "label": t.get("menu_section_applications", "Applications")})
            selector.extend(app_entries)

        # ------ role hubs (computed here so seen_roles is ready for the selector) ------
        # Each role hub is driven entirely by *_menu.json, using the same
        # filter_items / menu_is_visible mechanism as Path A — just applied
        # with a single-element role list so each hub shows exactly what
        # that role's menus declare, independent of DB permissions.
        seen_roles: List[str] = []
        role_hubs: Dict[str, List[Dict]] = {}

        for role_name in user_roles:
            r_hub: List[Dict] = []

            # Plugin menus first
            for plugin_id in self.loaded_plugins:
                for menu in raw.get(plugin_id, []):
                    if not menu_is_visible(menu, [role_name]):
                        continue
                    items = filter_items(menu.get("items", []), [role_name])
                    if items:
                        r_hub.append({
                            "id": menu["id"],
                            "label": t.get(menu["label_key"], menu["label_key"]),
                            "type": "Menu",
                            "items": translate_items(items, t),
                        })

            # Core non-System menus
            for menu in raw.get("core", []):
                if menu.get("type") == "System":
                    continue
                if not menu_is_visible(menu, [role_name]):
                    continue
                items = filter_items(menu.get("items", []), [role_name])
                if items:
                    r_hub.append({
                        "id": menu["id"],
                        "label": t.get(menu["label_key"], menu["label_key"]),
                        "type": "Menu",
                        "items": translate_items(items, t),
                    })

            # System (Help) menus last
            for menu in raw.get("core", []):
                if menu.get("type") != "System":
                    continue
                if not menu_is_visible(menu, [role_name]):
                    continue
                items = filter_items(menu.get("items", []), [role_name])
                if items:
                    r_hub.append({
                        "id": menu["id"],
                        "label": t.get(menu["label_key"], menu["label_key"]),
                        "type": "Menu",
                        "items": translate_items(items, t),
                    })

            if r_hub:
                seen_roles.append(role_name)
                role_hubs[role_name] = r_hub

        # Roles section — roles that have at least one visible menu item.
        if seen_roles:
            selector.append({"type": "separator"})
            selector.append({"type": "header", "label": t.get("menu_section_roles", "Roles")})
            for role in seen_roles:
                selector.append({"type": "item", "id": f"__role_{role}__", "label": role})

        # ------ hubs ------
        hubs: Dict[str, List] = {}

        # Identify System-type (Help) core menus for consistent ordering and
        # inclusion as the last item in every hub.
        core_menu_type: Dict[str, str] = {
            m["id"]: m.get("type", "") for m in raw.get("core", [])
        }
        core_help_menus = [
            m for m in translated.get("core", [])
            if core_menu_type.get(m["id"]) == "System"
        ]
        core_non_help_menus = [
            m for m in translated.get("core", [])
            if core_menu_type.get(m["id"]) != "System"
        ]

        # Default hub: plugins first, then core non-help, then Help last.
        default_hub: List[Dict] = []
        for plugin_id, plugin in self.loaded_plugins.items():
            if plugin_id in translated:
                all_items: List[Dict] = []
                for menu in translated[plugin_id]:
                    all_items.extend(menu["items"])
                if all_items:
                    display_label = (
                        plugin.manifest.get("display_name")
                        or plugin.manifest.get("name", plugin_id)
                    )
                    default_hub.append({"label": display_label, "type": "Menu", "items": all_items})
        for menu in core_non_help_menus:
            default_hub.append({"label": menu["label"], "type": "Menu", "items": menu["items"]})
        for menu in core_help_menus:
            default_hub.append({"label": menu["label"], "type": "Menu", "items": menu["items"]})
        hubs["__default__"] = default_hub

        # Per-AppLug hub: plugin menus followed by Help last.
        for plugin_id in self.loaded_plugins:
            if plugin_id in translated:
                hubs[plugin_id] = translated[plugin_id] + core_help_menus

        # Per-Role hub: built above from *_menu.json filtered per role.
        for role_name, r_hub in role_hubs.items():
            hubs[f"__role_{role_name}__"] = r_hub

        # Favorites hub — reserved for future use.
        hubs["__favorites__"] = []

        return {"selector": selector, "hubs": hubs}

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_loaded_plugins(self) -> List[Dict[str, str]]:
        """Returns a list of loaded plugins with their IDs and versions."""
        return [{"id": p.id, "version": p.version} for p in self.loaded_plugins.values()]
