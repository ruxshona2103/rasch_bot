"""Bazani birinchi marta tayyorlash: 11 jadval + public_id_seq.

Ishga tushirish: python -m scripts.init_db
Keyinchalik sxema o'zgarsa Alembic migratsiyalariga o'tish tavsiya etiladi —
bu skript faqat boshlang'ich (MVP) bosqich uchun.
"""

import asyncio

from db.engine import engine
from db.models import Base, public_id_seq


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(lambda sync_conn: public_id_seq.create(sync_conn, checkfirst=True))
    print("✅ Baza tayyor: 11 jadval + public_id_seq")


if __name__ == "__main__":
    asyncio.run(init_models())
