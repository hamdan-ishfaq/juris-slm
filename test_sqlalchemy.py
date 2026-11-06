import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_sqlalchemy():
    try:
        engine = create_async_engine(
            'postgresql+asyncpg://juris:juris_password@localhost:5433/juris_db',
            echo=False
        )
        async with engine.begin() as conn:
            result = await conn.execute(text('SELECT 1'))
            print('✓ SQLAlchemy async connection SUCCESS')
        await engine.dispose()
    except Exception as e:
        print(f'✗ SQLAlchemy async connection FAILED: {type(e).__name__}: {e}')

asyncio.run(test_sqlalchemy())
