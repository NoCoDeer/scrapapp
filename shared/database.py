"""
Утилиты для работы с базой данных.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
from typing import Generator
import logging

from .config import get_database_url
from .models import Base

logger = logging.getLogger(__name__)

# Создание движка базы данных
engine = create_engine(
    get_database_url(),
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False  # Установить в True для отладки SQL запросов
)

# Создание фабрики сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Создать все таблицы в базе данных."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Таблицы базы данных созданы успешно")
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
        raise


def drop_tables():
    """Удалить все таблицы из базы данных."""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Таблицы базы данных удалены успешно")
    except Exception as e:
        logger.error(f"Ошибка при удалении таблиц: {e}")
        raise


def get_db() -> Generator[Session, None, None]:
    """
    Получить сессию базы данных.
    Используется как dependency в FastAPI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Контекстный менеджер для работы с сессией базы данных.
    Используется в скрапере и других сервисах.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка в сессии базы данных: {e}")
        raise
    finally:
        db.close()


class DatabaseManager:
    """Менеджер для работы с базой данных."""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def create_session(self) -> Session:
        """Создать новую сессию."""
        return self.SessionLocal()
    
    def health_check(self) -> bool:
        """Проверить состояние подключения к базе данных."""
        try:
            with self.engine.connect() as connection:
                connection.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            return False
    
    def get_table_info(self) -> dict:
        """Получить информацию о таблицах."""
        try:
            with self.engine.connect() as connection:
                result = connection.execute("""
                    SELECT table_name, column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position
                """)
                
                tables = {}
                for row in result:
                    table_name = row[0]
                    if table_name not in tables:
                        tables[table_name] = []
                    tables[table_name].append({
                        'column': row[1],
                        'type': row[2]
                    })
                
                return tables
        except Exception as e:
            logger.error(f"Ошибка при получении информации о таблицах: {e}")
            return {}


# Глобальный экземпляр менеджера базы данных
db_manager = DatabaseManager()
