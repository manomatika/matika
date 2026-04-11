import os
import json
import logging
import importlib
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from .paths import ROOT_DIR
from .applug import BaseAppLug
from ..database import Role, Permission, PageType, PermissionLevel

logger = logging.getLogger(__name__)

class AppLugService:
    """
    Discovery and Registration Engine for Matika AppLugs.
    Scans ~/Matika/plugins/ for applug.json manifests.
    """
    
    def __init__(self, plugins_dir: Optional[str] = None):
        if plugins_dir is None:
            self.plugins_dir = os.path.join(ROOT_DIR, "plugins")
        else:
            self.plugins_dir = plugins_dir
        
        # In-memory storage of loaded plugins
        self.loaded_plugins: Dict[str, BaseAppLug] = {}
        
        # Ensure plugins directory exists
        os.makedirs(self.plugins_dir, exist_ok=True)

    def discover(self, db: Session) -> List[BaseAppLug]:
        """
        Scans for plugins and attempts to load them.
        """
        logger.info(f"Scanning for plugins in {self.plugins_dir}...")
        
        # For each subdirectory in plugins
        for plugin_name in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, plugin_name)
            if not os.path.isdir(plugin_path):
                continue
            
            # Use realpath for symlinks
            real_plugin_path = os.path.realpath(plugin_path)
                
            manifest_file = os.path.join(real_plugin_path, "applug.json")
            if not os.path.exists(manifest_file):
                continue
                
            try:
                with open(manifest_file, "r") as f:
                    manifest = json.load(f)
                
                plugin_id = manifest.get("id")
                if plugin_id in self.loaded_plugins:
                    continue # Already loaded
                
                # Load the entry point class
                entry_point = manifest.get("entry_point")
                if not entry_point:
                    logger.error(f"Plugin {plugin_name} is missing 'entry_point' in manifest.")
                    continue
                
                # Import the plugin class dynamically
                module_path, class_name = entry_point.rsplit(".", 1)
                
                # Ensure the plugin source directory is in sys.path
                import sys
                if real_plugin_path not in sys.path:
                    sys.path.insert(0, real_plugin_path)
                    
                module = importlib.import_module(module_path)
                plugin_class = getattr(module, class_name)
                
                # Instantiate and store
                plugin_instance = plugin_class(manifest)
                self.loaded_plugins[plugin_instance.id] = plugin_instance
                
                # Run standard registration logic (Roles, Permissions, Menu)
                self._register_plugin_entities(plugin_instance, db)
                
                # Fire the on_load hook
                plugin_instance.on_load(db)
                
                logger.info(f"Successfully loaded plugin: [PLUGIN:{plugin_instance.id}] v{plugin_instance.version}")
                
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                
        return list(self.loaded_plugins.values())

    def _register_plugin_entities(self, plugin: BaseAppLug, db: Session):
        """
        Auto-provisions Roles and Permissions defined in the manifest.
        """
        logger.info(f"[PLUGIN:{plugin.id}] Registering manifest entities...")
        
        # 1. Provision Roles/Permissions from manifest
        perms = plugin.manifest.get("permissions", [])
        for p in perms:
            path = p.get("page_path")
            ptype = p.get("page_type", "Maintenance")
            roles_map = p.get("roles", {})
            
            for role_name, level_name in roles_map.items():
                role = db.query(Role).filter(Role.name == role_name).first()
                if not role:
                    # Auto-create custom roles if they don't exist
                    role = Role(name=role_name, description=f"Auto-created for plugin {plugin.id}", is_system=False)
                    db.add(role)
                    db.flush()
                
                # Upsert permission
                level = getattr(PermissionLevel, level_name.upper(), PermissionLevel.NONE)
                existing_perm = db.query(Permission).filter(
                    Permission.page_path == path,
                    Permission.role_id == role.id
                ).first()
                
                if not existing_perm:
                    db.add(Permission(
                        page_path=path,
                        page_type=getattr(PageType, ptype.upper(), PageType.MAINTENANCE),
                        role_id=role.id,
                        level=level,
                        is_system=True # Plugin permissions are treated as framework-provisioned
                    ))
        
        db.commit()

    def get_all_menu_items(self) -> List[Dict[str, Any]]:
        """
        Aggregates menu items from all loaded plugins.
        """
        all_items = []
        for plugin in self.loaded_plugins.values():
            all_items.extend(plugin.get_menu_items())
        return all_items
