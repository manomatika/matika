import os
import logging
from abc import ABC, abstractmethod
from fastapi import APIRouter
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from .paths import get_matika_version

logger = logging.getLogger(__name__)


class BaseAppLug(ABC):
    """
    Abstract Base Class for all Matika AppLugs (Plugins).
    Plugins must subclass this and implement the required methods.

    Required applug.json fields (enforced at construction time):
      - matika_version: exact Matika version this AppLug was built and tested against.
        Must match the running Matika version exactly, or the AppLug is refused at startup.
        When MATIKA_ENV=development, a _dev suffix on the running version is stripped
        before comparison so local development against released applugs works.
    """

    def __init__(self, manifest: Dict[str, Any]):
        self.manifest = manifest
        self.id = manifest.get("id")
        self.version = manifest.get("version")
        self.matika_version = manifest.get("matika_version")
        self.router = APIRouter()
        self.templates = None  # Set by AppLugService
        self.app = None        # Set by AppLugService
        self._validate_compatibility()

    def _validate_compatibility(self) -> None:
        """
        Validates that this AppLug's declared matika_version matches the running
        Matika version. Raises RuntimeError on any mismatch so that AppLugService
        can log the failure and skip the plugin gracefully.

        When MATIKA_ENV=development, a _dev suffix on the running version is stripped
        before comparing. In all other environments strict exact matching is enforced.
        """
        running = get_matika_version()
        if not self.matika_version:
            raise RuntimeError(
                f"AppLug '{self.id}' is missing required field 'matika_version' in "
                f"applug.json. Set it to the exact Matika version this AppLug was built "
                f"and tested against (e.g. \"{running.removesuffix('_dev')}\")."
            )

        dev_mode = os.environ.get("MATIKA_ENV") == "development"
        is_dev_version = running.endswith("_dev")

        if dev_mode and is_dev_version:
            logger.warning(
                "Running in development mode — matika version check relaxed. "
                "Never use in production."
            )
            return

        if self.matika_version != running:
            raise RuntimeError(
                f"AppLug '{self.id}' declares matika_version='{self.matika_version}' "
                f"but running Matika {running}. Update applug.json to match the "
                f"installed Matika version before loading this AppLug."
            )

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
