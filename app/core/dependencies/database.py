# Standard libs
from typing import AsyncGenerator

# Non-Standard libs
from sqlalchemy.ext.asyncio import AsyncSession

# Own Modules
from db.session import async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
            yield session
