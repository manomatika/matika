from sqlalchemy.orm import Session
from matika.core.applug import BaseAppLug


class MinimalAppLug(BaseAppLug):
    """Deliberately minimal synthetic AppLug for use in framework-level tests."""

    def on_load(self, db: Session) -> None:
        pass

    def on_unload(self, db: Session) -> None:
        pass
