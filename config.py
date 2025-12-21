import os
from dotenv import load_dotenv

# .env 파일이 있으면 로컬 환경 변수로 로드
load_dotenv()

# 환경 변수에서 값을 가져오고, 없으면 기본값(또는 None) 사용
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///stella.db")