# app/db/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# 创建数据库引擎
# connect_args={"check_same_thread": False} 是 SQLite 特有的配置，允许多线程访问
engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)

# 创建会话工厂，用于后续在接口中获取数据库连接
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 定义所有模型类的基类
Base = declarative_base()

# 获取数据库会话的依赖函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()