from fastapi import APIRouter
from sqlalchemy.orm import Session
from matika.core.applug import BaseAppLug

router = APIRouter()

@router.get("/mock")
async def mock_route():
    return {"message": "Mock plugin is working"}

class MockPlugin(BaseAppLug):
    def on_load(self, db: Session):
        self.router.include_router(router)

    def on_unload(self, db: Session):
        pass
