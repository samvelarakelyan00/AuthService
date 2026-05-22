# Standard libs
from typing import AsyncGenerator

# Non-Standard libs
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = request.app.state.db_session_factory

    async with session_factory() as session:
            yield session
