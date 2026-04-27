from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, insert

from models.users import User


class UserCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_all_users(self):
        # result = await self.db.execute(text("""SELECT * FROM users"""))
        #
        # all_users = result.mappings().all()
        #
        # return all_users

        result = await self.db.execute(select(User))
        return result.scalars().all()

    async def get_all_users_by_token(self):
        result = await self.db.execute(text("""SELECT * FROM users"""))

        all_users = result.mappings().all()

        return all_users

        # result = await self.db.execute(select(User))
        # return result.scalars().all()
