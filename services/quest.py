import random
from typing import List, Tuple, Optional
from sqlalchemy import select
from sqlalchemy.ext.mutable import MutableList
from services.db import AsyncSessionLocal, User

class EconomyService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EconomyService, cls).__new__(cls)
            # 업적 정의
            cls._instance.achievements = [
                {"id": "first_win", "name": "첫 승리", "condition": lambda u: u.wins >= 1, "reward": 1000},
                {"id": "lucky_streak_3", "name": "3연승", "condition": lambda u: u.streak >= 3, "reward": 5000},
                {"id": "lucky_streak_5", "name": "5연승", "condition": lambda u: u.streak >= 5, "reward": 20000},
                {"id": "bad_luck_3", "name": "3연패", "condition": lambda u: u.streak <= -3, "reward": 3000},
            ]
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls()
        return cls._instance

    async def get_user(self, session, user_id: int) -> User:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                user_id=user_id,
                balance=10000,
                wins=0,
                losses=0,
                streak=0,
                max_risk_win=0.0,
                achievements=[],
                warnings=[],
                active_quest=None,
                gear_level=1,
                max_gear_level=1,
                gear_name="기본 장비",
                max_gambling_win=0,
                total_gambling_win=0,
                last_claim_time=None
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user

    async def get_balance(self, user_id: int) -> int:
        async with AsyncSessionLocal() as session:
            user = await self.get_user(session, user_id)
            return user.balance

    async def add_balance(self, user_id: int, amount: int):
        async with AsyncSessionLocal() as session:
            user = await self.get_user(session, user_id)
            user.balance += amount
            await session.commit()

    async def remove_balance(self, user_id: int, amount: int) -> bool:
        async with AsyncSessionLocal() as session:
            user = await self.get_user(session, user_id)
            if user.balance < amount:
                return False
            user.balance -= amount
            await session.commit()
            return True

    async def record_game_result(self, user_id: int, won: bool, amount: int = 0, risk: float = 0.5) -> List[str]:
        async with AsyncSessionLocal() as session:
            user = await self.get_user(session, user_id)
            notifications = []

            # 1. 스탯 업데이트
            if won:
                user.wins += 1
                user.streak = max(1, user.streak + 1)
                if risk < user.max_risk_win:
                    user.max_risk_win = risk
                
                # 누적 당첨금 기록
                user.total_gambling_win += amount

                # 최고 당첨금 기록
                if amount > user.max_gambling_win:
                    user.max_gambling_win = amount
                    notifications.append(f"✨ **도박 최고 당첨금 갱신!** (**{amount:,}원**)")
            else:
                user.losses += 1
                user.streak = min(-1, user.streak - 1)

            # 2. 업적 체크
            current_ach = list(user.achievements) if user.achievements else []
            for ach in self.achievements:
                if ach["id"] not in current_ach and ach["condition"](user):
                    current_ach.append(ach["id"])
                    user.balance += ach["reward"]
                    notifications.append(f"🏆 업적 달성: **{ach['name']}** (+{ach['reward']:,}원)")
            user.achievements = current_ach

            # 3. 퀘스트 체크 (추가된 부분)
            quest = user.active_quest
            if quest:
                if quest["type"] == "win_streak":
                    if won:
                        quest["current"] += 1
                        if quest["current"] >= quest["target"]:
                            user.balance += quest["reward"]
                            notifications.append(f"📜 퀘스트 완료! **{quest['target']}연승 도전** 성공! (+{quest['reward']:,}원)")
                            user.active_quest = None
                        else:
                            user.active_quest = quest # 진행 상황 업데이트
                    else:
                        user.balance = max(0, user.balance - quest["penalty"])
                        notifications.append(f"📜 퀘스트 실패... **{quest['target']}연승 도전** 실패 (-{quest['penalty']:,}원)")
                        user.active_quest = None

            session.add(user)
            await session.commit()
            return notifications

    async def assign_quest(self, user_id: int) -> Optional[dict]:
        """랜덤 퀘스트 부여"""
        async with AsyncSessionLocal() as session:
            user = await self.get_user(session, user_id)
            if user.active_quest:
                return None
            
            target_wins = random.randint(3, 5)
            quest = {
                "type": "win_streak",
                "target": target_wins,
                "current": 0,
                "reward": target_wins * 10000,
                "penalty": target_wins * 2000
            }
            user.active_quest = quest
            await session.commit()
            return quest

    async def get_quest(self, user_id: int) -> Optional[dict]:
        async with AsyncSessionLocal() as session:
            user = await self.get_user(session, user_id)
            return user.active_quest

    async def cancel_quest(self, user_id: int):
        async with AsyncSessionLocal() as session:
            user = await self.get_user(session, user_id)
            user.active_quest = None
            await session.commit()

    async def get_achievements_progress(self, user_id: int) -> List[dict]:
        """업적 목록과 달성 여부, 진행 상황을 반환합니다."""
        async with AsyncSessionLocal() as session:
            user = await self.get_user(session, user_id)
            user_ach = list(user.achievements) if user.achievements else []
            
            result = []
            for ach in self.achievements:
                progress_info = {
                    "id": ach["id"],
                    "name": ach["name"],
                    "reward": ach["reward"],
                    "completed": ach["id"] in user_ach,
                    "progress": "",
                }
                
                # 진행 상황 계산 (None 대비 안전한 처리)
                u_wins = user.wins or 0
                u_streak = user.streak or 0

                if ach["id"] == "first_win":
                    progress_info["progress"] = f"{min(u_wins, 1)}/1 승"
                elif ach["id"] == "lucky_streak_3":
                    progress_info["progress"] = f"{min(max(u_streak, 0), 3)}/3 연승"
                elif ach["id"] == "lucky_streak_5":
                    progress_info["progress"] = f"{min(max(u_streak, 0), 5)}/5 연승"
                elif ach["id"] == "bad_luck_3":
                    progress_info["progress"] = f"{min(abs(min(u_streak, 0)), 3)}/3 연패"
                
                result.append(progress_info)
            return result

    async def get_leaderboard(self) -> List[Tuple[int, int]]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.user_id, User.total_gambling_win)
                .where(User.total_gambling_win > 0)
                .order_by(User.total_gambling_win.desc())
                .limit(10)
            )
            return result.all()

    async def claim_reward(self, user_id: int) -> Tuple[bool, Optional[int]]:
        """10분마다 지원금 5,000원을 수령합니다."""
        from datetime import datetime, timedelta
        
        async with AsyncSessionLocal() as session:
            user = await self.get_user(session, user_id)
            now = datetime.now()
            
            if user.last_claim_time:
                cooldown = timedelta(minutes=10)
                next_claim = user.last_claim_time + cooldown
                if now < next_claim:
                    remaining = int((next_claim - now).total_seconds())
                    return False, remaining
            
            user.balance += 5000
            user.last_claim_time = now
            await session.commit()
            return True, None