from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import config

# SQLAlchemy 기본 설정
DATABASE_URL = config.DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

from sqlalchemy import Column, String, BigInteger, Integer, Float, JSON

# ... 기존 Base = declarative_base() 코드 아래에 추가

class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True) # 디스코드 유저 ID
    balance = Column(Integer, default=0)           # 잔고
    wins = Column(Integer, default=0)              # 승리 횟수
    losses = Column(Integer, default=0)            # 패배 횟수
    streak = Column(Integer, default=0)            # 연속 승리
    max_risk_win = Column(Float, default=0.0)      # 최고 리스크 승리
    achievements = Column(JSON, default=list)      # 업적 리스트 (JSON 형태로 저장)
    warnings = Column(JSON, default=list)          # 경고 리스트 (JSON 형태로 저장)
    active_quest = Column(JSON, nullable=True)     # 진행 중인 퀘스트 (JSON 형태로 저장)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
