"""Hard reset users table and seed owner/admin accounts."""
import asyncio
import sys
import os
from pathlib import Path
from sqlalchemy import delete

# Ensure backend/src is on path when running from repo root
THIS_FILE = Path(__file__).resolve()
BACKEND_ROOT = THIS_FILE.parents[1]
SRC_DIR = BACKEND_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from src.db import init_db, get_db, User, UserRole
from src.auth import get_password_hash, set_auth_config
from config import config

# Override database URL for local script execution (outside Docker)
# Use localhost:5432 when running from host machine
DATABASE_URL = os.getenv('DATABASE_URL') or config.auth.database_url.replace('db:', 'localhost:')



async def reset_and_seed():
    # Initialize DB and auth context with localhost URL for local execution
    await init_db(DATABASE_URL)
    set_auth_config(
        secret_key=config.auth.secret_key,
        algorithm=config.auth.algorithm,
        expire_minutes=config.auth.access_token_expire_minutes,
    )

    # Get session from the dependency generator
    session_gen = get_db()
    session = await session_gen.__anext__()
    
    try:
        # Wipe users table
        await session.execute(delete(User))
        await session.commit()

        # Seed accounts
        owner = User(
            email="owner@beweis.com",
            password_hash=get_password_hash("OwnerSecret123!"),
            role=UserRole.OWNER,
        )
        admin = User(
            email="admin@beweis.com",
            password_hash=get_password_hash("AdminSecret123!"),
            role=UserRole.ADMIN,
        )

        session.add_all([owner, admin])
        await session.commit()
        print("✅ Seeded owner@beweis.com and admin@beweis.com")
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(reset_and_seed())
