import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, BigInteger, Integer, Float, JSON, DateTime, Date
import config

# 1. 환경 변수에서 DATABASE_URL을 가져오되, Railway 설정을 우선합니다.
DATABASE_URL = os.getenv("DATABASE_URL")

# 진단용 출력 (배포 시 확인용)
print(f"[DB] 환경 변수 DATABASE_URL 존재 여부: {bool(DATABASE_URL)}")

# 2. 드라이버 설정 로직 추가
if DATABASE_URL and not DATABASE_URL.startswith("sqlite"):
    # Railway의 기본 postgres:// 주소를 SQLAlchemy가 인식하는 postgresql://로 변경합니다.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # 비동기 처리를 위해 드라이버(asyncpg)를 주소에 명시합니다.
    if "postgresql+asyncpg" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    print(f"[DB] PostgreSQL 모드로 연결 시도")
else:
    # 로컬 테스트용 (SQLite 비동기 드라이버 사용)
    DATABASE_URL = "sqlite+aiosqlite:///./stella.db"
    print(f"[DB] SQLite 모드로 연결 (로컬)")

# 3. SQLAlchemy 설정
engine = None
try:
    engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    print("[DB] ✅ 엔진 생성 성공")
except Exception as e:
    print(f"[DB] ❌ 데이터베이스 엔진 생성 실패: {e}")
    print(f"[DB] 사용된 URL: {DATABASE_URL[:50]}...")  # URL 일부만 출력 (보안)
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
    gear_level = Column(Integer, default=1)        # 현재 장비 레벨
    max_gear_level = Column(Integer, default=1)    # 역대 최고 장비 레벨
    gear_name = Column(String, default="기본 장비") # 장비 이름
    max_gambling_win = Column(Integer, default=0)   # 도박 최고 당첨금
    total_gambling_win = Column(Integer, default=0) # 도박 누적 당첨금
    last_claim_time = Column(DateTime, nullable=True) # 마지막 지원금 수령 시간
    last_attendance_date = Column(Date, nullable=True) # 마지막 출석 날짜
    attendance_streak = Column(Integer, default=0)     # 연속 출석 일수

async def apply_migrations():
    """누락된 컬럼을 자동으로 추가하는 마이그레이션 함수"""
    from sqlalchemy import text
    
    # 추가할 컬럼 정의 (이름, 타입)
    migrations = [
        ("gear_level", "INTEGER DEFAULT 1"),
        ("max_gear_level", "INTEGER DEFAULT 1"),
        ("gear_name", "VARCHAR DEFAULT '기본 장비'"),
        ("max_gambling_win", "INTEGER DEFAULT 0"),
        ("total_gambling_win", "INTEGER DEFAULT 0"),
        ("last_claim_time", "TIMESTAMP"),
        ("last_attendance_date", "DATE"),
        ("attendance_streak", "INTEGER DEFAULT 0")
    ]
    
    async with engine.connect() as conn:
        for col_name, col_type in migrations:
            try:
                # PostgreSQL/SQLite 모두 호환되는 컬럼 존재 확인 및 추가
                # 에러 발생 시(이미 존재할 때) 무시하도록 설계
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                print(f"[Migration] Added column: {col_name}")
            except Exception:
                # 이미 컬럼이 존재하는 경우 등
                pass
        await conn.commit()

# DB 초기화 함수
async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # 컬럼 마이그레이션 실행
        await apply_migrations()
        
        print("✅ 데이터베이스 초기화 및 마이그레이션 완료")
    except Exception as e:
        print(f"❌ 데이터베이스 초기화 실패: {e}")
        # gaierror 등 연결 오류 발생 시 여기서 캐치됨

# DB 세션 생성 함수
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session