# Rasch Mock-Test Bot

Arxitektura: `rasch_bot_yakuniy_arxitektura.md`.

## Hozirgi holat (Bosqich 1 — Ro'yxatdan o'tish)

Ishlaydi: `/start` → ism → telefon (faqat contact tugma orqali) → viloyat →
majburiy kanal a'zoligi tekshiruvi → `users` jadvaliga yozish → asosiy menyu.

Hali yo'q: to'lov/ID, PDF yuklash, Exam Mode, Rasch engine, admin panel,
scheduler, sertifikat, broadcast — bular navbatdagi bosqichlarda qo'shiladi
(`rasch_bot_yakuniy_arxitektura.md` VIII-qism bo'yicha).

## Ishga tushirish

1. PostgreSQL va Redis o'rnatilgan va ishga tushirilgan bo'lishi kerak.
2. `.env.example` dan `.env` yarating va to'ldiring:
   ```
   cp .env.example .env
   ```
3. Kutubxonalarni o'rnating:
   ```
   python -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
   (Python 3.10+ kerak. `pip`ni oldindan yangilamasangiz ba'zi paketlar uchun
   versiya konflikti chiqishi mumkin.)
4. Bazani tayyorlang (9 jadval + public_id_seq yaratiladi):
   ```
   python -m scripts.init_db
   ```
5. Botni ishga tushiring:
   ```
   python -m bot.main
   ```

## Loyiha strukturasi

To'liq reja `rasch_bot_yakuniy_arxitektura.md` VII-qismida. Hozircha
yaratilgan fayllar:

```
bot/
├── main.py
├── config.py
├── handlers/user/registration.py
├── keyboards/{registration,main_menu}.py
├── states/registration.py
└── middlewares/db.py
core/
└── channel.py            # kanal a'zoligini tekshirish (get_chat_member)
db/
├── models.py              # SQLAlchemy — 9 jadval + public_id_seq
├── engine.py
└── queries.py
scripts/
└── init_db.py
```
