import asyncio
import asyncpg

async def test_conn():
    try:
        conn = await asyncpg.connect(
            user='juris',
            password='juris_password',
            database='juris_db',
            host='localhost',
            port=5433
        )
        print('✓ Direct asyncpg connection SUCCESS')
        await conn.close()
    except Exception as e:
        print(f'✗ Direct asyncpg connection FAILED: {type(e).__name__}: {e}')

asyncio.run(test_conn())
