import logging
from abc import ABC, abstractmethod
from fastapi import APIRouter
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from .paths import get_matika_version, version_core, is_prerelease

logger = logging.getLogger(__name__)


class BaseAppLug(ABC):
    """
    Abstract Base Class for all Matika AppLugs (Plugins).
    Plugins must subclass this and implement the required methods.

    Required applug.json fields (enforced at construction time):
      - matika_version: the bare-core (X.Y.Z) Matika framework version this AppLug
        was built and tested against. Compared on CORE: the pre-release suffix
        (e.g. -dev, -rc.N) is stripped from BOTH the running version and the
        declared matika_version before equality. So a pre-release runtime such as
        0.0.4-dev or 0.0.4-rc.1 loads an AppLug pinned to bare core 0.0.4.
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
        Validates that this AppLug's declared matika_version is compatible with the
        running Matika version. Comparison is on the bare CORE (X.Y.Z): the
        pre-release suffix (-dev, -rc.N, ...) is stripped from BOTH the running
        version and the declared matika_version before equality.

        This gives general pre-release awareness: a pre-release runtime such as
        0.0.4-dev or 0.0.4-rc.1 is allowed to load an AppLug pinned to bare core
        0.0.4 — they share the same core. There is no separate development escape
        hatch; the ladder X.Y.Z-dev < X.Y.Z-rc.N < X.Y.Z all resolve to core X.Y.Z.

        Raises RuntimeError on any core mismatch so that AppLugService can log the
        failure and skip the plugin gracefully.
        """
        running = get_matika_version()
        if not self.matika_version:
            raise RuntimeError(
                f"AppLug '{self.id}' is missing required field 'matika_version' in "
                f"applug.json. Set it to the bare-core (X.Y.Z) Matika framework "
                f"version this AppLug was built and tested against "
                f"(e.g. \"{version_core(running)}\")."
            )

        running_core = version_core(running)
        declared_core = version_core(self.matika_version)

        if declared_core != running_core:
            raise RuntimeError(
                f"AppLug '{self.id}' declares matika_version='{self.matika_version}' "
                f"(core {declared_core}) but running Matika {running} (core "
                f"{running_core}). Update applug.json to match the installed Matika "
                f"version core before loading this AppLug."
            )

        if is_prerelease(running):
            logger.warning(
                "Running Matika %s is a pre-release — AppLug '%s' loaded by core "
                "match (%s). Never ship a pre-release runtime to production.",
                running, self.id, running_core,
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
