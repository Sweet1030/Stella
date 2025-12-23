import random
from typing import Tuple, Optional, Dict, Any
from sqlalchemy import select
from services.db import AsyncSessionLocal, User


class UpgradeService:
    """장비 강화 시스템 서비스"""
    _instance = None

    # 등급 정보: (등급명, 레벨 범위, 성공확률 범위, 성공 비중, 하락 가중치, 파괴 확률)
    TIERS = {
        "Rookie":    {"range": (1, 20),   "success": (1.00, 0.85), "gains": (0.40, 0.35, 0.25), "drops": None,              "destroy": 0.00},
        "Common":    {"range": (21, 40),  "success": (0.80, 0.60), "gains": (0.40, 0.35, 0.25), "drops": (0.60, 0.40, 0.00), "destroy": 0.00},
        "Rare":      {"range": (41, 60),  "success": (0.55, 0.35), "gains": (0.60, 0.30, 0.10), "drops": (0.70, 0.25, 0.05), "destroy": 0.00},
        "Epic":      {"range": (61, 70),  "success": (0.30, 0.20), "gains": (0.60, 0.30, 0.10), "drops": (0.70, 0.25, 0.05), "destroy": 0.01},
        "Legendary": {"range": (71, 80),  "success": (0.18, 0.12), "gains": (0.80, 0.15, 0.05), "drops": (0.50, 0.35, 0.15), "destroy": 0.03},
        "Mythic":    {"range": (81, 90),  "success": (0.10, 0.05), "gains": (0.80, 0.15, 0.05), "drops": (0.30, 0.40, 0.30), "destroy": 0.07},
        "Ascension": {"range": (91, 100), "success": (0.03, 0.01), "gains": (1.00, 0.00, 0.00), "drops": None,              "destroy": 1.00},
    }

    # 비용 범위 (레벨 구간별)
    COST_RANGES = {
        (1, 20):   (500, 7000),
        (21, 40):  (10000, 40000),
        (41, 60):  (60000, 150000),
        (61, 70):  (250000, 600000),
        (71, 80):  (1000000, 3000000),
        (81, 90):  (7000000, 20000000),
        (91, 100): (50000000, 100000000),
    }

    TIER_COLORS = {
        "Rookie": 0x808080,     # 회색
        "Common": 0x00FF00,     # 초록
        "Rare": 0x0080FF,       # 파랑
        "Epic": 0x8000FF,       # 보라
        "Legendary": 0xFFD700,  # 금색
        "Mythic": 0xFF0000,     # 빨강
        "Ascension": 0xFF00FF,  # 마젠타
    }

    TIER_EMOJIS = {
        "Rookie": "⚪",
        "Common": "🟢",
        "Rare": "🔵",
        "Epic": "🟣",
        "Legendary": "🟡",
        "Mythic": "🔴",
        "Ascension": "💎",
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UpgradeService, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls()
        return cls._instance

    def get_tier_name(self, level: int) -> str:
        """레벨에 해당하는 등급명 반환"""
        for tier_name, info in self.TIERS.items():
            if info["range"][0] <= level <= info["range"][1]:
                return tier_name
        return "Ascension"

    def get_tier_info(self, level: int) -> Dict[str, Any]:
        """레벨에 해당하는 등급 정보 반환"""
        tier_name = self.get_tier_name(level)
        return {"name": tier_name, **self.TIERS[tier_name]}

    def calculate_cost(self, level: int) -> int:
        """레벨에 따른 강화 비용 계산"""
        for (min_lv, max_lv), (min_cost, max_cost) in self.COST_RANGES.items():
            if min_lv <= level <= max_lv:
                # 구간 내 레벨에 비례하여 비용 증가
                progress = (level - min_lv) / max(1, (max_lv - min_lv))
                return int(min_cost + (max_cost - min_cost) * progress)
        return 50000000  # 기본값 (91+)

    def calculate_success_rate(self, level: int, bonus: float = 0.0) -> float:
        """레벨에 따른 성공 확률 계산 (보너스 포함)"""
        tier = self.get_tier_info(level)
        min_lv, max_lv = tier["range"]
        max_rate, min_rate = tier["success"]  # 레벨이 올라갈수록 확률 감소
        
        progress = (level - min_lv) / max(1, (max_lv - min_lv))
        base_rate = max_rate - (max_rate - min_rate) * progress
        
        return min(1.0, base_rate + bonus)

    def _weighted_choice(self, weights: Tuple[float, ...], values: Tuple[int, ...]) -> int:
        """가중치 기반 선택"""
        roll = random.random()
        cumulative = 0.0
        for weight, value in zip(weights, values):
            cumulative += weight
            if roll < cumulative:
                return value
        return values[-1]

    async def get_user_gear(self, user_id: int) -> Tuple[int, int, str]:
        """유저의 장비 정보 조회 (현재 레벨, 최고 레벨, 장비 이름)"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            if user:
                return user.gear_level or 1, user.max_gear_level or 1, user.gear_name or "기본 장비"
            return 1, 1, "기본 장비"

    async def set_gear_name(self, user_id: int, name: str):
        """장비 이름을 설정합니다."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.gear_name = name
                await session.commit()

    async def get_balance(self, user_id: int) -> int:
        """유저의 잔액 조회"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            if user:
                return user.balance or 0
            return 0

    async def upgrade(self, user_id: int, bonus: float = 0.0) -> Dict[str, Any]:
        """
        강화 실행
        Returns: {
            "success": bool,
            "destroyed": bool,
            "old_level": int,
            "new_level": int,
            "cost": int,
            "rate": float,
            "change": int,  # 레벨 변화량 (+1, +2, +3, -1, -2, -3, 0)
            "new_record": bool,  # 신기록 여부
        }
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                # 유저가 없으면 생성
                user = User(
                    user_id=user_id,
                    balance=10000,
                    gear_level=1,
                    max_gear_level=1
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            old_level = user.gear_level or 1
            cost = self.calculate_cost(old_level)
            
            # 잔액 확인
            if user.balance < cost:
                return {
                    "success": False,
                    "destroyed": False,
                    "old_level": old_level,
                    "new_level": old_level,
                    "cost": cost,
                    "rate": 0,
                    "change": 0,
                    "new_record": False,
                    "error": "insufficient_balance"
                }
            
            # 최대 레벨 체크
            if old_level >= 100:
                return {
                    "success": False,
                    "destroyed": False,
                    "old_level": old_level,
                    "new_level": old_level,
                    "cost": cost,
                    "rate": 0,
                    "change": 0,
                    "new_record": False,
                    "error": "max_level"
                }
            
            # 비용 차감
            user.balance -= cost
            
            tier = self.get_tier_info(old_level)
            success_rate = self.calculate_success_rate(old_level, bonus)
            roll = random.random()
            
            new_level = old_level
            destroyed = False
            change = 0
            
            if roll < success_rate:
                # 성공!
                gain = self._weighted_choice(tier["gains"], (1, 2, 3))
                new_level = min(100, old_level + gain)
                change = new_level - old_level
            else:
                # 실패
                destroy_rate = tier["destroy"]
                if random.random() < destroy_rate:
                    # 파괴!
                    destroyed = True
                    new_level = 1
                    change = 1 - old_level
                elif tier["drops"] is not None:
                    # 하락
                    # drops = (유지확률, -1확률, -2확률) 또는 (유지확률, -1확률, 나머지)
                    # Common: (0.60, 0.40, 0.00) -> 유지 60%, -1 40%
                    maintain_chance = tier["drops"][0]
                    drop1_chance = tier["drops"][1]
                    # 나머지는 -2 또는 -3
                    
                    drop_roll = random.random()
                    if drop_roll < maintain_chance:
                        # 유지
                        change = 0
                    elif drop_roll < maintain_chance + drop1_chance:
                        # -1
                        new_level = max(1, old_level - 1)
                        change = new_level - old_level
                    else:
                        # Rare 이상: 하락 가중치 적용
                        tier_name = tier["name"]
                        if tier_name in ["Rare", "Epic"]:
                            drop = self._weighted_choice((0.70, 0.25, 0.05), (1, 2, 3))
                        elif tier_name == "Legendary":
                            drop = self._weighted_choice((0.50, 0.35, 0.15), (1, 2, 3))
                        elif tier_name == "Mythic":
                            drop = self._weighted_choice((0.30, 0.40, 0.30), (1, 2, 3))
                        else:
                            drop = 1
                        new_level = max(1, old_level - drop)
                        change = new_level - old_level
                # Rookie, Ascension: drops가 None이면 유지 또는 파괴만
            
            # 레벨 업데이트
            user.gear_level = new_level
            new_record = False
            if new_level > (user.max_gear_level or 1):
                user.max_gear_level = new_level
                new_record = True
            
            await session.commit()
            
            return {
                "success": change > 0,
                "destroyed": destroyed,
                "old_level": old_level,
                "new_level": new_level,
                "cost": cost,
                "rate": success_rate,
                "change": change,
                "new_record": new_record
            }

    async def get_leaderboard(self) -> list:
        """장비 레벨 랭킹 TOP 10"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.user_id, User.gear_level, User.max_gear_level, User.gear_name)
                .where(User.gear_level > 1)
                .order_by(User.gear_level.desc())
                .limit(10)
            )
            return result.all()
