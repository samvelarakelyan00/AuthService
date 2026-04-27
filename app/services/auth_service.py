from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, insert

from core.security import Security

from models.users import User

from schemas.user_schemas import (
    UserCreateSchema,
    UserOutSchema,
    UserLoginSchema
)

from schemas.token_schemas import (
    AccessTokenOutSchema,
    AccessTokenPayloadDataSchema
)


class AuthService:
    def __init__(self, db: AsyncSession, security: Security) -> None:
        self.db = db
        self.security = security

    async def signup(self, user_create_data: UserCreateSchema) -> UserOutSchema:
        # hashed_password = await run_in_threadpool(
        #     self.security.get_password_hash,
        #     user_create_data.plain_password
        # )
        #
        # result = await self.db.execute(text("""INSERT INTO users (username, email, hashed_password)
        #                                        VALUES (:name, :email, :hashed_password) RETURNING *"""),
        #                                {"name": user_create_data.username,
        #                                "email": user_create_data.email,
        #                                "hashed_password": hashed_password})
        #
        # new_user = result.mappings().one()
        #
        # await self.db.commit()
        #
        # return UserOutSchema.model_validate(new_user)

        # --------------- SqlAlchemy -------------
        hashed_password = await run_in_threadpool(
            self.security.get_password_hash,
            user_create_data.plain_password
        )

        stmt = (
            insert(User)
            .values(
                username=user_create_data.username,
                email=user_create_data.email,
                hashed_password=hashed_password
            )
            .returning(User)
        )

        result = await self.db.execute(stmt)
        new_user_model = result.scalar_one()

        await self.db.commit()

        return UserOutSchema.model_validate(new_user_model)

    async def login(self, user_login_data: UserLoginSchema) -> AccessTokenOutSchema:
        # result = await self.db.execute(text("""SELECT
        #                                             user_id,
        #                                             username,
        #                                             email,
        #                                             hashed_password
        #                                        FROM users
        #                                        WHERE email = :email"""),
        #                 {"email": user_login_data.email})
        #
        # user = result.fetchone()
        #
        # if user is None:
        #     raise HTTPException(
        #         status_code=status.HTTP_401_UNAUTHORIZED,
        #         detail="Invalid email or password"
        #     )
        #
        # db_user_password = user.hashed_password
        #
        # password_correct = await run_in_threadpool(
        #     self.security.verify_password,
        #     user_login_data.password,
        #     db_user_password
        # )
        #
        # if not password_correct:
        #     raise HTTPException(
        #         status_code=status.HTTP_401_UNAUTHORIZED,
        #         detail="Invalid email or password"
        #     )
        #
        # access_token_payload_data = AccessTokenPayloadDataSchema(
        #     user_id=str(user.user_id),
        #     user_email=user.email,
        # )
        # access_token = self.security.create_access_token(
        #     payload_data=access_token_payload_data
        # )
        #
        # return AccessTokenOutSchema.model_validate(
        #     {
        #         "access_token": access_token,
        #         "token_type": "Bearer"
        #     }
        # )

        stmt = (
            select(User)
            .where(
                User.email == user_login_data.email
            )
        )

        result = await self.db.execute(stmt)
        user: User | None = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        hashed_password = user.hashed_password

        password_correct = await run_in_threadpool(
            self.security.verify_password,
            user_login_data.password,
            hashed_password
        )

        if not password_correct:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        user_id = str(user.user_id)
        access_token = self.security.create_access_token(
            user_id=user_id
        )

        return AccessTokenOutSchema.model_validate(
            {
                "access_token": access_token,
                "token_type": "Bearer"
            }
        )
