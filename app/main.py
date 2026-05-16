from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from sqlalchemy import text

from db.session import create_postgres_engine, create_postgres_sessionmaker
from db.redis_connection import init_redis_client

from api.v1 import v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Инициализация инфраструктуры...")

    # 1. Настройка Postgres
    engine = create_postgres_engine()
    session_factory = create_postgres_sessionmaker(engine)
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    # Верификация Postgres
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    print("✅ Postgres подключен и верифицирован!")

    # 2. Настройка Redis
    redis_client = init_redis_client()
    app.state.redis_client = redis_client

    # Верификация Redis
    await redis_client.ping()
    print("✅ Redis подключен и верифицирован!")

    yield  # Приложение работает и принимает запросы

    print("🛑 Закрытие соединений...")
    # Корректное закрытие Postgres
    await app.state.db_engine.dispose()

    # Корректное закрытие Redis
    await app.state.redis_client.close()
    await app.state.redis_client.connection_pool.disconnect()
    print("💤 Все соединения безопасно закрыты.")


app = FastAPI(lifespan=lifespan)


app.include_router(v1_router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
