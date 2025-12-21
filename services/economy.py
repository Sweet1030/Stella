import json
import os
from typing import Dict, List, Optional, Tuple

DATA_FILE = "economy_data.json"

class EconomyService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EconomyService, cls).__new__(cls)
            cls._instance.data = cls._instance._load_data()
            cls._instance.achievements = [
                {"id": "first_win", "name": "첫 승리", "condition": lambda stats: stats["wins"] >= 1, "reward": 1000},
                {"id": "lucky_streak_3", "name": "3연승", "condition": lambda stats: stats["streak"] >= 3, "reward": 5000},
                {"id": "lucky_streak_5", "name": "5연승", "condition": lambda stats: stats["streak"] >= 5, "reward": 20000},
                {"id": "bad_luck_3", "name": "3연패", "condition": lambda stats: abs(stats["streak"]) >= 3 and stats["streak"] < 0, "reward": 3000},
                {"id": "high_roller", "name": "고위험군 승리", "condition": lambda stats: stats.get("max_risk_win", 0) <= 0.1, "reward": 50000},
            ]
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls() # Creates instance
        return cls._instance

    def _load_data(self) -> Dict:
        if not os.path.exists(DATA_FILE):
            return {}
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _save_data(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def get_user_data(self, user_id: int) -> Dict:
        uid = str(user_id)
        if uid not in self.data:
            self.data[uid] = {
                "balance": 10000,
                "stats": {"wins": 0, "losses": 0, "streak": 0, "max_risk_win": 1.0},
                "achievements": [],
                "active_quest": None  # {target: int, current: int, reward: int, penalty: int, type: "win_streak"}
            }
            self._save_data()
        return self.data[uid]

    def get_balance(self, user_id: int) -> int:
        return self.get_user_data(user_id)["balance"]

    def add_balance(self, user_id: int, amount: int):
        data = self.get_user_data(user_id)
        data["balance"] += amount
        self._save_data()

    def remove_balance(self, user_id: int, amount: int) -> bool:
        data = self.get_user_data(user_id)
        if data["balance"] < amount:
            return False
        data["balance"] -= amount
        self._save_data()
        # print(f"[Economy] Deducted {amount} from {user_id}. New Balance: {data['balance']}")
        return True

    def record_game_result(self, user_id: int, won: bool, risk: float = 0.5) -> List[str]:
        """
        Updates stats, checks achievements, and updates quest progress.
        Returns a list of notification strings (achievements/quest completions).
        """
        data = self.get_user_data(user_id)
        stats = data["stats"]
        notifications = []

        # Update basic stats
        if won:
            stats["wins"] += 1
            if stats["streak"] < 0: stats["streak"] = 0
            stats["streak"] += 1
            if risk < stats.get("max_risk_win", 1.0):
                stats["max_risk_win"] = risk
        else:
            stats["losses"] += 1
            if stats["streak"] > 0: stats["streak"] = 0
            stats["streak"] -= 1

        # Check Achievements
        user_achievements = data["achievements"]
        for ach in self.achievements:
            if ach["id"] not in user_achievements and ach["condition"](stats):
                user_achievements.append(ach["id"])
                data["balance"] += ach["reward"]
                notifications.append(f"🏆 업적 달성: **{ach['name']}** (+{ach['reward']}원)")

        # Check Active Quest
        quest = data.get("active_quest")
        if quest:
            if quest["type"] == "win_streak":
                if won:
                    quest["current"] += 1
                    if quest["current"] >= quest["target"]:
                        data["balance"] += quest["reward"]
                        notifications.append(f"📜 퀘스트 완료! **{quest['target']}연승 도전** 성공! (+{quest['reward']}원)")
                        data["active_quest"] = None
                else:
                    data["balance"] -= quest["penalty"]
                    if data["balance"] < 0: data["balance"] = 0 # Prevent debt
                    notifications.append(f"📜 퀘스트 실패... **{quest['target']}연승 도전** 실패 (-{quest['penalty']}원)")
                    data["active_quest"] = None

        self._save_data()
        return notifications

    def get_leaderboard(self) -> List[Tuple[str, int]]:
        """Returns top 10 users by balance"""
        sorted_users = sorted(
            self.data.items(), 
            key=lambda x: x[1]["balance"], 
            reverse=True
        )
        return [(uid, d["balance"]) for uid, d in sorted_users[:10]]

    def assign_quest(self, user_id: int) -> Optional[dict]:
        """Assigns a random quest if user doesn't have one."""
        data = self.get_user_data(user_id)
        if data.get("active_quest"):
            return None
        
        # Simple quest logic: Win X times in a row
        import random
        target_wins = random.randint(3, 5)
        reward = target_wins * 10000
        penalty = target_wins * 2000
        
        quest = {
            "type": "win_streak",
            "target": target_wins,
            "current": 0,
            "reward": reward,
            "penalty": penalty
        }
        data["active_quest"] = quest
        self._save_data()
        return quest

    def get_quest(self, user_id: int) -> Optional[dict]:
        return self.get_user_data(user_id).get("active_quest")
