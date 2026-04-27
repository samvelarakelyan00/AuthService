from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from sqlalchemy import text

from db.session import async_engine

from api.v1 import v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        print("Server Starts...")
        async with async_engine.connect() as conn:
            await conn.execute(text("""SELECT 1"""))
        print("Database Connection Verified!")

        yield
    finally:
        await async_engine.dispose()
        print("Pool Connections are closed!")


app = FastAPI(lifespan=lifespan)


app.include_router(v1_router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
