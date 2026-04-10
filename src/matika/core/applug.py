from abc import ABC, abstractmethod
from fastapi import APIRouter
from sqlalchemy.orm import Session
from typing import Dict, Any, List

class BaseAppLug(ABC):
    """
    Abstract Base Class for all Matika AppLugs (Plugins).
    Plugins must subclass this and implement the required methods.
    """
    
    def __init__(self, manifest: Dict[str, Any]):
        self.manifest = manifest
        self.id = manifest.get("id")
        self.version = manifest.get("version")
        self.router = APIRouter()

    @abstractmethod
    def on_load(self, db: Session):
        """
        Called when the plugin is discovered and loaded.
        Use this to register routes, models, or seed initial data.
        """
        pass

    @abstractmethod
    def on_unload(self, db: Session):
        """
        Called when the plugin is being unloaded (optional cleanup).
        """
        pass

    def get_router(self) -> APIRouter:
        """Returns the FastAPI router for this plugin."""
        return self.router

    def get_menu_items(self) -> List[Dict[str, Any]]:
        """Returns menu items defined in the manifest."""
        return self.manifest.get("menu_items", [])
