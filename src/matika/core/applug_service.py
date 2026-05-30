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

        The Admin dropdown is aggregated from System (core) items and any plugin
        admin-role items.  SectionHeader items separate sources when two or more
        contribute to a single dropdown.  Single-source dropdowns never receive
        headers.

        System items always appear first; plugins follow in discovery order.

        Returns:
            {
                "selector": [ {id, label, type}, ... ],
                "hubs":     { hub_id: [ menu_item, ... ], ... }
            }
        """
        all_menus = self.menu_loader.load_menus()

        # ------ extract core menu sections -------
        core_data = all_menus.get("core", {})
        core_admin_role = core_data.get("roles", {}).get("Admin")   # Dict or None
        core_system = core_data.get("system")                        # Dict or None

        # ------ admin dropdown label -------
        admin_label: str = t.get("menu_admin", "Admin")
        if core_admin_role:
            admin_label = t.get(core_admin_role["label_key"], admin_label)

        # ------ system items (visible only to Admin role holders) -------
        system_items: List[Dict] = []
        if "Admin" in user_roles and core_admin_role:
            filtered = filter_items(core_admin_role.get("items", []), user_roles)
            if filtered:
                system_items.extend(translate_items(filtered, t))

        # ------ translate core help (system) menu -------
        translated_help_menus: List[Dict] = []
        if core_system:
            filtered = filter_items(core_system.get("items", []), user_roles)
            if filtered:
                translated_help_menus.append({
                    "id": core_system["id"],
                    "label": t.get(core_system["label_key"], core_system["label_key"]),
                    "type": "Menu",
                    "items": translate_items(filtered, t),
                })

        # ------ plugin app menus and plugin admin items -------
        plugin_app_translated: Dict[str, Dict] = {}
        # {plugin_id: {"label": display_name, "items": [translated items]}}
        plugin_admin_items: Dict[str, Dict] = {}

        for plugin_id, plugin in self.loaded_plugins.items():
            display_name = (
                plugin.manifest.get("display_name")
                or plugin.manifest.get("name", plugin_id)
            )

            app_section = all_menus.get(plugin_id, {}).get("application")
            if app_section:
                filtered = filter_items(app_section.get("items", []), user_roles)
                if filtered:
                    plugin_app_translated[plugin_id] = {
                        "id": app_section.get("id", plugin_id),
                        "label": t.get(app_section["label_key"], app_section["label_key"]),
                        "type": "Menu",
                        "items": translate_items(filtered, t),
                    }

            # Admin role items collected only when the user holds the Admin role.
            if "Admin" in user_roles:
                admin_entry = all_menus.get(plugin_id, {}).get("roles", {}).get("Admin")
                if admin_entry:
                    filtered = filter_items(admin_entry.get("items", []), user_roles)
                    if filtered:
                        plugin_admin_items[plugin_id] = {
                            "label": display_name,
                            "items": translate_items(filtered, t),
                        }

        # ------ helper: assemble Admin dropdown -------
        def _build_admin_dropdown(
            incl_system: bool,
            plugin_ids: Optional[List[str]] = None,
        ) -> Optional[Dict]:
            """
            Aggregate sources into a single Admin dropdown.
            incl_system  — include System (core) items.
            plugin_ids   — restrict to these plugins (None = all in load order).
            Returns None when no items are available for the current user.
            One source → no SectionHeaders.
            Two or more sources → SectionHeader items separate each source.
            """
            sources: List[tuple] = []
            if incl_system and system_items:
                sources.append(("System", system_items))

            ids = plugin_ids if plugin_ids is not None else list(self.loaded_plugins.keys())
            for pid in ids:
                entry = plugin_admin_items.get(pid)
                if entry and entry["items"]:
                    sources.append((entry["label"], entry["items"]))

            if not sources:
                return None

            if len(sources) == 1:
                items: List[Dict] = list(sources[0][1])
            else:
                items = []
                for label, src_items in sources:
                    items.append({"type": "SectionHeader", "label": label})
                    items.extend(src_items)

            return {"type": "Menu", "label": admin_label, "items": items}

        # ------ selector ------
        selector: List[Dict] = [
            {"type": "item", "id": "__default__", "label": t.get("menu_type_default", "Default")},
            {"type": "separator"},
            {"type": "item", "id": "__favorites__", "label": t.get("menu_type_favorites", "Favorites")},
        ]

        app_entries: List[Dict] = []
        for plugin_id, plugin in self.loaded_plugins.items():
            if plugin_id in plugin_app_translated:
                label = (
                    plugin.manifest.get("display_name")
                    or plugin.manifest.get("name", plugin_id)
                )
                app_entries.append({"type": "item", "id": plugin_id, "label": label})

        if app_entries:
            selector.append({"type": "separator"})
            selector.append({"type": "header", "label": t.get("menu_section_applications", "Applications")})
            selector.extend(app_entries)

        # ------ role hubs -------
        # Every role the user holds appears in the selector.
        # Admin hub: aggregated Admin dropdown (System + all plugins).
        # Other role hubs: core Role-type menus + plugin role menus + Help.
        seen_roles: List[str] = []
        role_hubs: Dict[str, List[Dict]] = {}

        for role_name in user_roles:
            r_hub: List[Dict] = []

            if role_name == "Admin":
                admin_dd = _build_admin_dropdown(incl_system=True)
                if admin_dd:
                    r_hub.append(admin_dd)
            else:
                core_role_entry = all_menus.get("core", {}).get("roles", {}).get(role_name)
                if core_role_entry:
                    items = filter_items(core_role_entry.get("items", []), [role_name])
                    if items:
                        r_hub.append({
                            "id": core_role_entry["id"],
                            "label": t.get(core_role_entry["label_key"], core_role_entry["label_key"]),
                            "type": "Menu",
                            "items": translate_items(items, t),
                        })
                for pid in self.loaded_plugins:
                    role_entry = all_menus.get(pid, {}).get("roles", {}).get(role_name)
                    if not role_entry:
                        continue
                    items = filter_items(role_entry.get("items", []), user_roles)
                    if items:
                        r_hub.extend(translate_items(items, t))

            # Help always last in every role hub.
            r_hub.extend(translated_help_menus)

            seen_roles.append(role_name)
            role_hubs[role_name] = r_hub

        if seen_roles:
            selector.append({"type": "separator"})
            selector.append({"type": "header", "label": t.get("menu_section_roles", "Roles")})
            for role in seen_roles:
                selector.append({"type": "item", "id": f"__role_{role}__", "label": role})

        # ------ hubs ------
        hubs: Dict[str, List] = {}

        # Default hub: plugin app dropdowns → Admin (aggregated) → Help.
        default_hub: List[Dict] = []
        for plugin_id, plugin in self.loaded_plugins.items():
            if plugin_id in plugin_app_translated:
                display_label = (
                    plugin.manifest.get("display_name")
                    or plugin.manifest.get("name", plugin_id)
                )
                tm = plugin_app_translated[plugin_id]
                default_hub.append({"label": display_label, "type": "Menu", "items": tm["items"]})

        admin_dd = _build_admin_dropdown(incl_system=True)
        if admin_dd:
            default_hub.append(admin_dd)

        default_hub.extend(translated_help_menus)
        hubs["__default__"] = default_hub

        # Per-AppLug hub: plugin app menu → plugin-only Admin (single source) → Help.
        for plugin_id in self.loaded_plugins:
            if plugin_id not in plugin_app_translated:
                continue
            plugin_hub: List[Dict] = [plugin_app_translated[plugin_id]]
            plugin_admin_dd = _build_admin_dropdown(incl_system=False, plugin_ids=[plugin_id])
            if plugin_admin_dd:
                plugin_hub.append(plugin_admin_dd)
            plugin_hub.extend(translated_help_menus)
            hubs[plugin_id] = plugin_hub

        # Per-Role hub.
        for role_name, r_hub in role_hubs.items():
            hubs[f"__role_{role_name}__"] = r_hub

        hubs["__favorites__"] = []

        return {"selector": selector, "hubs": hubs}

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_loaded_plugins(self) -> List[Dict[str, str]]:
        """Returns a list of loaded plugins with their IDs and versions."""
        return [{"id": p.id, "version": p.version} for p in self.loaded_plugins.values()]
