# Rasch Mock-Test Bot

Milliy sertifikat mock-test Telegram boti (Rasch modeli asosida). Arxitektura:
`rasch_bot_yakuniy_arxitektura.md`.

## Hozirgi holat

Ishlaydi: ro'yxatdan o'tish, to'lov (chek → admin tasdig'i → unikal ID),
admin panel (test yaratish — PDF/qo'lda, testlar boshqaruvi, to'lovlar,
statistika, broadcast), scheduler (avtopilot/qo'lda boshlash-yakunlash),
Exam Mode (savol-javob, Navigator, taymer), Rasch Engine (JMLE/MLE, 75-shkala,
daraja, reyting).

Hali yo'q: apellyatsiya paneli, sertifikat PNG generatsiyasi, misfit
statistikasi, Click/Payme integratsiyasi.

## Lokal ishga tushirish

1. PostgreSQL va Redis kerak (Docker orqali eng oson).
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
4. Bazani tayyorlang:
   ```
   python -m scripts.init_db
   ```
5. Botni ishga tushiring:
   ```
   python -m bot.main
   ```

## Production'ga joylash (DigitalOcean Droplet)

Bitta oddiy Droplet yetarli (tavsiya: Ubuntu 24.04, kamida 2GB RAM) — bot,
PostgreSQL va Redis bir xil serverda, Docker orqali ishlaydi. Alohida
"Managed Database" yoki "Managed Redis" xarid qilish shart emas — Droplet'ning
o'zidagi disk (SSD) barcha ma'lumotlar (baza + savol rasmlari) uchun yetarli.

**1) Serverga ulanish va Docker o'rnatish**
```bash
ssh root@SIZNING_SERVER_IP

curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin git
```

**2) Loyihani GitHub'dan olish**
```bash
git clone https://github.com/ruxshona2103/rasch_bot.git
cd rasch_bot
```

**3) `.env` faylini serverga moslab to'ldirish**
```bash
cp .env.example .env
nano .env
```
Muhim: `DB_HOST`/`REDIS_HOST`ni docker-compose o'zi to'g'rilaydi (o'zgartirish
shart emas) — faqat `BOT_TOKEN`, `ADMIN_IDS`, `CHANNEL_ID`, `CARD_NUMBER`,
`DB_PASSWORD` kabi haqiqiy qiymatlarni kiriting.

**4) Ishga tushirish**
```bash
docker compose up -d --build
```
Bu buyruq PostgreSQL, Redis va botni birga qurib, fonda doimiy ishga
tushiradi (`restart: unless-stopped` — server qayta yuklansa ham o'zi qayta
ko'tariladi).

**5) Loglarni ko'rish**
```bash
docker compose logs -f bot
```

**6) Yangilash (kodni o'zgartirgach)**
```bash
git pull
docker compose up -d --build
```

**7) Kunlik zaxira (backup)**
```bash
crontab -e
```
Va shu qatorni qo'shing (har kuni soat 03:00 da):
```
0 3 * * * /root/rasch_bot/scripts/backup.sh >> /root/rasch_bot/backup.log 2>&1
```

## Loyiha strukturasi

To'liq reja `rasch_bot_yakuniy_arxitektura.md` VII-qismida.

```
bot/
├── main.py                      # dispatcher, scheduler, routerlar
├── config.py
├── filters/admin.py
├── handlers/
│   ├── user/                    # registration, tests_list, exam, cabinet
│   └── admin/                   # test_create, test_manage, payments, stats, broadcast, panel
├── keyboards/
├── states/
└── middlewares/                 # db session, nav-reset
core/
├── rasch.py                     # JMLE, MLE, 75-shkala, daraja
├── scheduler.py                 # avtopilot (APScheduler)
├── pdf_parser.py                # PDF -> PNG
├── answer_key.py                # kalit parse, normalizatsiya
├── channel.py                   # kanal a'zoligi tekshiruvi
└── storage.py                   # savol rasmlarini diskka saqlash
db/
├── models.py                    # SQLAlchemy — 9 jadval + public_id_seq
├── engine.py
└── queries.py
scripts/
├── init_db.py
└── backup.sh
Dockerfile
docker-compose.yml
```
