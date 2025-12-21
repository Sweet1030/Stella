import asyncio
import json
import os
from services.db import AsyncSessionLocal, User, init_db

async def migrate_data():
    # 1. DB 테이블 생성 확인
    await init_db()
    
    # 2. JSON 파일 읽기
    json_path = "economy_data.json"
    if not os.path.exists(json_path):
        print("JSON 파일을 찾을 수 없습니다.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    async with AsyncSessionLocal() as session:
        for user_str_id, info in data.items():
            user_id = int(user_str_id)
            
            # 이미 DB에 있는지 확인
            existing_user = await session.get(User, user_id)
            if existing_user:
                continue

            # 새 유저 객체 생성
            new_user = User(
                user_id=user_id,
                balance=info.get("balance", 0),
                wins=info.get("stats", {}).get("wins", 0),
                losses=info.get("stats", {}).get("losses", 0),
                streak=info.get("stats", {}).get("streak", 0),
                max_risk_win=info.get("stats", {}).get("max_risk_win", 0.0),
                achievements=info.get("achievements", [])
            )
            session.add(new_user)
        
        await session.commit()
        print("데이터 이관이 완료되었습니다!")

if __name__ == "__main__":
    asyncio.run(migrate_data())