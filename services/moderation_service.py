import datetime
from sqlalchemy import select
from services.db import AsyncSessionLocal, User
from services.economy import EconomyService

class ModerationService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModerationService, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls()
        return cls._instance
    
    def __init__(self):
        self.economy = EconomyService.get_instance()

    async def add_warning(self, user_id: int, reason: str, moderator_id: int) -> int:
        """경고를 추가하고 누적 경고 수를 반환합니다."""
        async with AsyncSessionLocal() as session:
            user = await self.economy.get_user(session, user_id)
            
            warning = {
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "reason": reason,
                "moderator_id": moderator_id
            }
            
            # JSON 리스트 복사 후 추가 (SQLAlchemy 감지용)
            current_warnings = list(user.warnings) if user.warnings else []
            current_warnings.append(warning)
            user.warnings = current_warnings
            
            await session.commit()
            return len(current_warnings)

    async def get_warnings(self, user_id: int) -> list:
        async with AsyncSessionLocal() as session:
            user = await self.economy.get_user(session, user_id)
            return user.warnings if user.warnings else []

    async def clear_warnings(self, user_id: int):
        async with AsyncSessionLocal() as session:
            user = await self.economy.get_user(session, user_id)
            user.warnings = []
            await session.commit()
