# Этот файл — реэкспорт из app.core.database
# Оставлен для обратной совместимости
from app.core.database import (
    AsyncSessionLocal,
    Base,
    engine,
    get_db,
    init_db,
)

__all__ = ["Base", "engine", "AsyncSessionLocal", "get_db", "init_db"]
