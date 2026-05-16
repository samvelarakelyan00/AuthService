from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, insert
import redis.asyncio as aioredis

import jwt

from core.security import Security
from core.config import settings

from models.users import User

from schemas.user_schemas import (
    UserCreateSchema,
    UserOutSchema,
    UserLoginSchema
)

from schemas.token_schemas import (
    AccessTokenOutSchema,
    RefreshTokenOutSchema,
    TokenOutSchema,
    AccessTokenPayloadDataSchema
)


class AuthService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis, security: Security) -> None:
        self.db = db
        self.redis = redis
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

    async def login(self, user_login_data: UserLoginSchema):
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

        stmt = select(User).where(User.email == user_login_data.email)
        result = await self.db.execute(stmt)
        user: User | None = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        password_correct = await run_in_threadpool(
            self.security.verify_password, user_login_data.password, user.hashed_password
        )
        if not password_correct:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        user_id = str(user.user_id)

        access_data = self.security.create_access_token(user_id=user_id)
        refresh_data = self.security.create_refresh_token(user_id=user_id)

        # Запись в Redis Whitelist
        redis_key = f"auth:refresh:{user_id}:{refresh_data['jti']}"
        await self.redis.set(redis_key, "active", ex=refresh_data["ttl_seconds"])

        # Адаптировано под ваши RootModel-схемы (передаем только строки token)
        return TokenOutSchema(
            access_token=access_data["token"],
            refresh_token=refresh_data["token"]
        )

    async def refresh_tokens(self, refresh_token_str: str) -> TokenOutSchema:
        try:
            payload = self.security.verify_token(refresh_token_str, expected_type="refresh")
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(err))

        user_id = payload.get("sub")
        token_jti = payload.get("jti")

        redis_key = f"auth:refresh:{user_id}:{token_jti}"

        # Получаем статус токена
        token_status = await self.redis.get(redis_key)

        if not token_status:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid or expired")

        # Если токен уже был использован в течение последних 15 секунд (Race Condition)
        if token_status == "rotated":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token already rotated. Please reuse the new pair."
            )

        # Создаем новые токены
        new_access_data = self.security.create_access_token(user_id=user_id)
        new_refresh_data = self.security.create_refresh_token(user_id=user_id)

        new_redis_key = f"auth:refresh:{user_id}:{new_refresh_data['jti']}"

        # Паттерн: Grace Period Rotation через транзакцию (Pipeline)
        async with self.redis.pipeline(transaction=True) as pipe:
            # Вместо удаления даем старому токену 15 секунд "дожить" для параллельных запросов фронтенда
            await pipe.set(redis_key, "rotated", ex=15)
            # Записываем новый токен в Whitelist
            await pipe.set(new_redis_key, "active", ex=new_refresh_data["ttl_seconds"])
            await pipe.execute()

        return TokenOutSchema(
            access_token=new_access_data["token"],
            refresh_token=new_refresh_data["token"]
        )

    async def logout(self, refresh_token_str: str) -> None:
        """
        Мгновенный и гарантированный отзыв токена из Redis (Enterprise Idempotent Logout).
        Зачищает Redis даже если токен истек по времени или находится в статусе rotated.
        """
        try:
            # 1. Сначала пытаемся строго верифицировать токен (проверка подписи)
            payload = self.security.verify_token(refresh_token_str, expected_type="refresh")
            user_id = payload.get("sub")
            token_jti = payload.get("jti")
        except ValueError as err:
            # 2. Если ошибка "Token has expired", нам ВСЁ РАВНО нужно узнать jti, чтобы удалить его из Redis.
            # Мы делаем небезопасный декод БЕЗ проверки времени жизни (exp), но строго проверяем структуру.
            if "expired" in str(err):
                try:
                    # Декодируем без валидации времени, но с проверкой подписи SECRET_KEY
                    payload = jwt.decode(
                        refresh_token_str,
                        key=settings.tokens.SECRET_KEY.get_secret_value(),
                        algorithms=[settings.tokens.ALGORITHM],
                        options={"verify_exp": False}  # Игнорируем время истечения
                    )
                    user_id = payload.get("sub")
                    token_jti = payload.get("jti")
                except Exception:
                    # Если токен сломан криптографически (неверная подпись) — просто выходим
                    return
            else:
                # Если токен вообще невалиден (Invalid token / тип не тот) — выходим
                return

        # 3. Гарантированное удаление ключа из Redis
        if user_id and token_jti:
            redis_key = f"auth:refresh:{user_id}:{token_jti}"
            await self.redis.delete(redis_key)
            print(f"🔒 Сессия auth:refresh:{user_id}:{token_jti} успешно удалена при Logout.")

    async def logout_from_all_devices(self, user_id: str) -> None:
        """
        Полный сброс всех активных сессий пользователя (например, при смене пароля).
        """
        pattern = f"auth:refresh:{user_id}:*"

        # Находим все ключи сессий данного пользователя
        # На продакшене KEYS использовать нельзя (блокирует поток Redis), используем SCAN
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
            if keys:
                await self.redis.delete(*keys)
            if cursor == 0:
                break
        print(f"🚨 Все сессии пользователя {user_id} были принудительно аннулированы.")
