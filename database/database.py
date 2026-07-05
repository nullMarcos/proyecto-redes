import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Se lee la URL de la base de datos de la variable de entorno o se usa SQLite por defecto
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./monitoreo_industrial.db") 

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    """Clase base declarativa para todos los modelos de SQLAlchemy"""
    pass

def get_db():
    """Dependencia para los endpoints HTTP de FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()