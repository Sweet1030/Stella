import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, BigInteger, Integer, Float, JSON
import config

# 1. 환경 변수에서 DATABASE_URL을 가져오되, Railway 설정을 우선합니다.
DATABASE_URL = os.getenv("DATABASE_URL")

# 2. 드라이버 설정 로직 추가
if DATABASE_URL and not DATABASE_URL.startswith("sqlite"):
    # Railway의 기본 postgres:// 주소를 SQLAlchemy가 인식하는 postgresql://로 변경합니다.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # 비동기 처리를 위해 드라이버(asyncpg)를 주소에 명시합니다.
    if "postgresql+asyncpg" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    # 로컬 테스트용 (SQLite 비동기 드라이버 사용)
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./stella.db")

# 3. SQLAlchemy 설정
try:
    engine = create_async_engine(DATABASE_URL, echo=True)
except Exception as e:
    print(f"❌ 데이터베이스 엔진 생성 실패: {e}")
    # 엔진 생성 실패 시 폴백 (메모리 DB 등) 처리가 필요할 수 있으나 여기서는 로그만 남김
    raise e
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# 유저 테이블 정의
class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True) # 디스코드 유저 ID
    balance = Column(Integer, default=0)           # 잔고
    wins = Column(Integer, default=0)              # 승리 횟수
    losses = Column(Integer, default=0)            # 패배 횟수
    streak = Column(Integer, default=0)            # 연속 승리
    max_risk_win = Column(Float, default=0.0)      # 최고 리스크 승리
    achievements = Column(JSON, default=list)      # 업적 리스트
    warnings = Column(JSON, default=list)          # 경고 리스트
    active_quest = Column(JSON, nullable=True)     # 진행 중인 퀘스트

# DB 초기화 함수
async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ 데이터베이스 초기화 완료")
    except Exception as e:
        print(f"❌ 데이터베이스 초기화 실패: {e}")
        # gaierror 등 연결 오류 발생 시 여기서 캐치됨

# DB 세션 생성 함수
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session