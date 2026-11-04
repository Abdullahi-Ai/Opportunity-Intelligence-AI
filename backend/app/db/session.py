import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from app.config import settings

def normalize_database_url(url: str) -> str:
    """
    Normalizes database connection URLs for SQLAlchemy and Psycopg 2 compatibility.

    Guarantees:
    - 'postgres://' -> 'postgresql+psycopg2://'
    - 'postgresql://' -> 'postgresql+psycopg2://'
    - 'postgresql+psycopg://' -> 'postgresql+psycopg2://'
    - 'postgresql+psycopg2://' -> unchanged
    - 'sqlite://...' -> unchanged
    - Only modifies the scheme prefix, leaving credentials and query params untouched.
    """
    if not url:
        return url
    if url.startswith("postgresql+psycopg2://"):
        return url
    elif url.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg2://" + url[len("postgresql+psycopg://"):]
    elif url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url

db_url = normalize_database_url(settings.DATABASE_URL)

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    kwargs = {"connect_args": connect_args, "echo": False}
    if ":memory:" in db_url:
        from sqlalchemy.pool import StaticPool
        kwargs["poolclass"] = StaticPool
    engine = create_engine(db_url, **kwargs)
elif "-pooler." in db_url or os.environ.get("VERCEL"):
    engine = create_engine(
        db_url,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
        echo=False
    )
else:
    engine = create_engine(
        db_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"connect_timeout": 10},
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
