# Standard libs
import logging
from datetime import datetime, timedelta, timezone

# Non-Standard libs
from sqlalchemy import delete

# Own Modules
from db.session import db_manager
from models import User


logger = logging.getLogger(__name__)


async def cleanup_unverified_users() -> int:
    """
    Deletes unverified users who signed up more than 3 days ago.
    Returns the number of deleted rows.
    """
    # Get current UTC time, make it naive to match DB column type
    now_utc_aware = datetime.now(timezone.utc)
    cutoff_utc_naive = (now_utc_aware - timedelta(days=3)).replace(tzinfo=None)

    logger.info(
        "Starting cleanup of unverified users created before %s",
        cutoff_utc_naive.isoformat()
    )

    async with db_manager.session_factory() as session:
        stmt = delete(User).where(
            User.is_active == False,
            User.created_at < cutoff_utc_naive
        )
        result = await session.execute(stmt)
        await session.commit()

        deleted_count = result.rowcount
        logger.info(
            "Cleanup completed: %d unverified user(s) deleted.",
            deleted_count
        )
        return deleted_count