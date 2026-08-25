# 🎓 MILLIY SERTIFIKAT MOCK-TEST BOTI — YAKUNIY ARXITEKTURA (v2)
### Rasch modeli asosida ishlaydigan Telegram test tizimi | Matematika

> Ushbu hujjat barcha kelishuvlarning yakuniy, to'liq versiyasi. 
> 🆕 belgisi bilan tekshiruv paytida topilgan, avval unutilgan qismlar ko'rsatilgan.

---

# I QISM. ASOS

## 1. Loyiha maqsadi

O'zbekiston Milliy sertifikat imtihonini (matematika) to'liq imitatsiya qiluvchi Telegram bot:

- Natijalar **xalqaro Rasch modeli** asosida (rasmiy metodika)
- Maksimal ball: **75** | Darajalar: A+ (70+), A (65–69,9), B+ (60–64,9), B (55–59,9), C+ (50–54,9), C (46–49,9)
- Test tarkibi: **45 savol** = 35 yopiq (A/B/C/D) + 10 ochiq (raqamli javob)
- Ikki rejim: **🔴 Jonli mock** (belgilangan vaqtda, umumiy reyting) va **📚 Arxiv** (istalgan vaqt, arzonroq, mashq)
- Botda ochiq yoziladi: bu **norasmiy mock**, BBA'ga aloqasi yo'q (huquqiy himoya)

## 2. Texnologiyalar

| Qatlam | Texnologiya | Vazifasi |
|---|---|---|
| Bot | **aiogram 3.x** (async) | Telegram interfeysi, FSM |
| Backend | **FastAPI** | Rasch engine servisi, kelajakda web-admin |
| Baza | **PostgreSQL** | Doimiy ma'lumotlar |
| Kesh | **Redis** | 🆕 FAQAT FSM storage + UI-kesh (render/keyboard keshi). Javob va urinish holati Redis'da SAQLANMAYDI — yagona haqiqat manbai har doim PostgreSQL. Redis o'chib qolsa faqat FSM (qaysi menyudaligi) yo'qoladi, javoblar yo'qolmaydi |
| Rejalashtiruvchi | **APScheduler** | Avtopilot (ochish/yopish/hisoblash) |
| PDF → rasm | **PyMuPDF (fitz)** | Savol sahifalarini PNG ga aylantirish |
| Rasch | **NumPy** | JMLE / MLE, 75-shkala |
| Sertifikat | **Pillow** | Natija PNG generatsiya |

🆕 **Vaqt zonasi:** barcha vaqtlar serverda **Asia/Tashkent (UTC+5)** da saqlanadi va ko'rsatiladi. Server UTC da ishlasa ham, scheduler va deadline'lar timezone-aware qilinadi — aks holda test 5 soat surilib ketish xavfi bor.

## 3. Umumiy komponentlar

```
O'quvchi (Telegram) ──┐
                      ├──> aiogram Bot ──> PostgreSQL (9 jadval)
Admin (Telegram)  ────┘        │
                               ├──> Redis (FSM, jonli holat)
                               ├──> APScheduler (avtopilot)
                               └──> Rasch Engine (NumPy)
```

---

# II QISM. MA'LUMOTLAR BAZASI (9 jadval)

```sql
-- 1. FOYDALANUVCHILAR
CREATE TABLE users (
    user_pk        SERIAL PRIMARY KEY,
    public_id      INT UNIQUE,               -- 🎫 UNIKAL ID (1000, 1001...) —
                                             --    birinchi to'lov tasdiqlanganda beriladi.
                                             --    🆕 Postgres SEQUENCE (public_id_seq, START 1000)
                                             --    orqali beriladi — nextval() atomik, ikki admin
                                             --    bir vaqtda ikki xil userni tasdiqlasa ham
                                             --    dublikat ID chiqmaydi (MAX()+1 EMAS).
                                             --    Berilgach umrbod O'ZGARMAYDI (immutable, qayta
                                             --    berilmaydi, hech qanday admin amali uni almashtira olmaydi)
    telegram_id    BIGINT UNIQUE NOT NULL,
    full_name      VARCHAR(120) NOT NULL,
    phone          VARCHAR(20)  NOT NULL,
    region         VARCHAR(60),
    is_blocked     BOOLEAN DEFAULT FALSE,    -- 🆕 botni bloklagan. Broadcast (outbox)dan tashqari
                                             --    HAR QANDAY individual xabar yuborishda ham
                                             --    Telegram "Forbidden" xatosi ushlansa darhol TRUE
                                             --    qilinadi (faqat outbox emas)
    created_at     TIMESTAMP DEFAULT NOW()
);

-- 2. TESTLAR (narxni HAR TEST uchun admin belgilaydi)
CREATE TABLE tests (
    test_id        SERIAL PRIMARY KEY,
    title          VARCHAR(200) NOT NULL,
    subject        VARCHAR(50) DEFAULT 'matematika',  -- 🆕 kelajakda boshqa fanlar
    mode           VARCHAR(10)  NOT NULL,             -- 'jonli' | 'arxiv'
    price          INT NOT NULL,                      -- 💰 shu testning O'Z narxi
    duration_min   INT NOT NULL,
    start_at       TIMESTAMPTZ,                       -- jonli: 12.02 20:00 (+05)
    deadline_at    TIMESTAMPTZ,                       -- jonli: 12.02 22:00 (+05)
    video_url      TEXT,                              -- 🆕 video yechim havolasi
    status         VARCHAR(20) DEFAULT 'tayyorlanmoqda',
      -- tayyorlanmoqda | rejalashtirilgan | jonli_davom | hisoblanmoqda |
      -- yakunlangan | arxivda | bekor_qilingan (🆕)
    calibrated     BOOLEAN DEFAULT FALSE,
    created_at     TIMESTAMP DEFAULT NOW()
);

-- 3. SAVOLLAR
CREATE TABLE questions (
    question_id    SERIAL PRIMARY KEY,
    test_id        INT REFERENCES tests(test_id),
    order_num      INT NOT NULL,             -- 1..45
    text           TEXT,                     -- matnli savol (NULL mumkin)
    image_file_id  VARCHAR(200),             -- Telegram file_id kesh (NULL mumkin)
    qtype          VARCHAR(10) NOT NULL,     -- 'yopiq' | 'ochiq'
    correct_answer TEXT NOT NULL,            -- 'A' | '12' | '0.5|1/2'
    b_difficulty   FLOAT,                    -- Rasch qiyinligi (kalibrlashdan keyin)
    is_excluded    BOOLEAN DEFAULT FALSE     -- 🆕 apellyatsiyada chiqarilgan savol
);

-- 4. TO'LOVLAR (har to'lov ANIQ BITTA testga bog'lanadi!)
CREATE TABLE payments (
    payment_id      SERIAL PRIMARY KEY,
    user_pk         INT REFERENCES users(user_pk),
    test_id         INT REFERENCES tests(test_id),   -- 🔒 qaysi testga to'landi
    receipt_file_id VARCHAR(200) NOT NULL,
    receipt_hash    VARCHAR(64),              -- 🆕 chek dublikatini aniqlash (file_unique_id)
    amount          INT,
    status          VARCHAR(15) DEFAULT 'kutilmoqda',
                    -- kutilmoqda | tasdiqlangan | rad_etilgan
    reject_reason   TEXT,
    admin_id        BIGINT,
    decided_at      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 5. CHIPTALAR (kirish huquqi — QAT'IY: 1 to'lov = 1 test)
CREATE TABLE purchases (
    purchase_id    SERIAL PRIMARY KEY,
    user_pk        INT REFERENCES users(user_pk),
    test_id        INT REFERENCES tests(test_id),
    payment_id     INT REFERENCES payments(payment_id),
    UNIQUE (user_pk, test_id)          -- 🔒 baza darajasida dublikat imkonsiz
);

-- 6. URINISHLAR
CREATE TABLE attempts (
    attempt_id     SERIAL PRIMARY KEY,
    user_pk        INT REFERENCES users(user_pk),
    test_id        INT REFERENCES tests(test_id),
    kind           VARCHAR(10) NOT NULL,     -- 'jonli' | 'arxiv'
    started_at     TIMESTAMPTZ NOT NULL,
    deadline_at    TIMESTAMPTZ NOT NULL,     -- faqat server hisoblaydi
    finished_at    TIMESTAMPTZ,
    status         VARCHAR(15) DEFAULT 'davom_etmoqda',
                   -- davom_etmoqda | yakunlangan | vaqt_tugagan
    theta          FLOAT,
    ball_75        FLOAT,
    grade          VARCHAR(3),
    rank_position  INT,                      -- faqat jonli uchun
    UNIQUE (user_pk, test_id)          -- 🔒 bitta urinish
);

-- 7. JAVOBLAR (har bosish darhol shu yerga)
CREATE TABLE answers (
    attempt_id     INT REFERENCES attempts(attempt_id),
    question_id    INT REFERENCES questions(question_id),
    answer         TEXT,
    updated_at     TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (attempt_id, question_id)
);

-- 🆕 8. ADMIN HARAKATLARI JURNALI (audit)
CREATE TABLE admin_log (
    log_id      SERIAL PRIMARY KEY,
    admin_id    BIGINT NOT NULL,
    action      VARCHAR(50) NOT NULL,   -- payment_approve, payment_reject,
                                        -- test_create, test_cancel, key_fix, recalc...
    target      TEXT,                   -- payment_id=514 / test_id=5 / question_id=12
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 🆕 9. XABARNOMALAR NAVBATI (broadcast throttling uchun)
CREATE TABLE outbox (
    id          SERIAL PRIMARY KEY,
    user_pk     INT REFERENCES users(user_pk),
    payload     JSONB NOT NULL,          -- xabar turi va matni
    status      VARCHAR(10) DEFAULT 'navbatda',  -- navbatda | yuborildi | xato
    created_at  TIMESTAMP DEFAULT NOW()
);
```

---

# III QISM. USER TOMONI — BOSHIDAN OXIRIGACHA

## 1. Ro'yxatdan o'tish (`/start`)

```
Bot: Assalomu alaykum! Milliy sertifikat mock-test botiga xush kelibsiz.
     Ism-familiyangizni kiriting:
User: Aliyev Vali
Bot: Telefon raqamingizni yuboring: [ 📱 Raqamni ulashish ]  (contact tugma —
     qo'lda yozilgan raqam qabul qilinmaydi, soxtalashga qarshi)
Bot: Viloyatingizni tanlang: [Toshkent] [Samarqand] ...
```

🆕 **Majburiy kanal a'zoligi** (marketing uchun): ro'yxat oxirida bot kanalga a'zolikni tekshiradi (`get_chat_member`). A'zo bo'lmasa: `📢 Davom etish uchun kanalimizga a'zo bo'ling: [Kanal] [✅ Tekshirish]`.

```
Bot: ✅ Ro'yxatdan o'tdingiz!
     ℹ️ Unikal ID birinchi to'lovingiz tasdiqlangach beriladi.
```

→ `users` ga yoziladi, `public_id = NULL`.

## 2. Asosiy menyu

```
[ 🔴 Jonli testlar ]   [ 📚 Arxiv testlar ]
[ 👤 Kabinetim ]       [ 📊 Natijalarim ]
[ 🎥 Video yechimlar ] [ ℹ️ Yordam / Aloqa ]
```

## 3. TO'LOV VA ID BERILISHI

### Qat'iy printsip: 1 to'lov = 1 test = 1 chipta

- "Umumiy obuna" tushunchasi **yo'q**. Har to'lov aniq `test_id` ga mixlanadi
- Mock #5 ga to'lagan o'quvchi Mock #6 ga **hech qanday huquq olmaydi**
- Narxni **har test uchun admin o'zi belgilaydi** (`tests.price`)
- ID — shaxsiy doimiy raqam, lekin u **kirish huquqi EMAS**; huquq faqat chipta

### Jarayon qadam-baqadam

**1)** O'quvchi testni tanlaydi:

```
🔴 Mock #5 — Matematika
📅 12-fevral 20:00–22:00 | 💰 15 000 so'm   ← shu testning o'z narxi
[ 💳 To'lov qilish ]
```

**2)** Bot yo'riqnoma beradi, FSM `waiting_receipt(test_id=5)` holatiga o'tadi — chek boshidanoq shu testga bog'lanadi:

```
💳 To'lov tartibi:
1️⃣ 9860 xxxx xxxx xxxx (Karta egasi) kartasiga 15 000 so'm o'tkazing
2️⃣ Chek (skrinshot) rasmini SHU YERGA yuboring
⏳ Admin 30 daqiqa ichida tekshiradi
```

**3)** Chek keldi → `payments` (kutilmoqda, `test_id=5`, `receipt_hash` saqlanadi).
🆕 **Dublikat himoyasi:** shu `receipt_hash` avval ishlatilgan bo'lsa, adminga qizil ogohlantirish chiqadi: `⚠️ BU CHEK AVVAL YUBORILGAN (payment #480)!`
🆕 **Spam himoyasi:** userning shu `test_id` bo'yicha allaqachon `kutilmoqda` holatidagi cheki bo'lsa, yangi chek qabul qilinmaydi: `⏳ Oldingi chekingiz hali tekshirilmoqda, iltimos kuting`.

**4)** Adminga darhol push:

```
🔔 YANGI TO'LOV #514
[chek rasmi]
👤 Aliyev Vali | 📱 +998 90 ... | 🆕 Birinchi to'lov (ID yo'q)
🧪 Test: Mock #5 | Kutilgan summa: 15 000
[ ✅ Tasdiqlash ]   [ ❌ Rad etish ]
```

🆕 **Bir vaqtda ikki bosish himoyasi:** hozircha bitta admin nazorat qiladi, lekin kelajakda ko'p admin bo'lsa ham xato chiqmasligi uchun tasdiqlash/rad etish har doim atomik `UPDATE payments SET status=... WHERE payment_id=... AND status='kutilmoqda'` shaklida bajariladi. Kim birinchi bossa — shu qabul qilinadi, 0 qator o'zgargan bo'lsa ikkinchi admin ekranida darhol: `⚠️ Bu chek allaqachon hal qilingan` chiqadi va tugmalar o'chadi (qayta so'ralmaydi).

**5a) Admin ✅** — bitta DB tranzaksiyada:
1. `payments.status = 'tasdiqlangan'`
2. `public_id IS NULL` bo'lsa → yangi ID (1000+ ketma-ket)
3. `purchases` ga chipta `(user, test_id=5)`
4. `admin_log` ga yozuv
5. O'quvchiga:

```
✅ To'lovingiz tasdiqlandi!
🎫 Sizning unikal ID: 1047
   (doimiy raqam — barcha testlarda shu; reytingda ism o'rniga chiqadi)
🔴 Mock #5 ga kirish ochildi. 12-fevral 20:00 da shu botda boshlanadi!
```

**5b) Admin ❌** → sabab tanlaydi (summa kam / chek soxta / boshqa) → o'quvchiga xabar + qayta urinish imkoni.

**Takroriy to'lovlarda** ID berilmaydi — mavjud ID ga faqat yangi chipta qo'shiladi.
**Jonli testga to'lov qabuli 20:00 da avtomatik yopiladi.**

### ID nima uchun kerak (eslatma)

1. To'lov-huquq belgisi (tasdiqlangan ishtirokchi)
2. Reytingda anonimlik (ism o'rniga ID)
3. Doimiy identifikatsiya (username o'zgarsa ham tarix saqlanadi)
4. Firibgarlikka qarshi (telefon + telegram_id + ID bog'lami)
5. Apellyatsiya/qo'llab-quvvatlashda tez qidiruv

## 4. Jonli test kuni (avtopilot jadvali)

| Vaqt | Avtomatik harakat |
|---|---|
| **19:30** | Chiptasi borlarga eslatma: `🔔 ID: 1047 — 30 daqiqa qoldi!` |
| **20:00** | To'lov qabuli yopiladi + hammaga `[ ▶️ TESTNI BOSHLASH ]` |
| **20:00–22:00** | Exam Mode |
| **22:00** | Barcha ochiq urinishlar avto-yakunlanadi |
| **22:05** | Rasch (JMLE) → natijalar, sertifikatlar, kanal reytingi |

🆕 **Ommaviy yuborish cheklovi:** Telegram ~30 xabar/soniya ruxsat beradi. 500+ ishtirokchiga xabarlar `outbox` navbati orqali 25 msg/s tezlikda yuboriladi (20:00 dagi start xabari ~20 soniyada hammaga yetadi). Bloklagan userlar `is_blocked=TRUE` belgilanadi.

### `▶️` bosilganda server tekshiruvi (ID qo'lda yozilmaydi!)

```python
0. 🆕 kanalga a'zolikmi hali ham bormi? (get_chat_member qayta tekshiriladi —
      ro'yxatdan o'tgach chiqib ketgan bo'lishi mumkin)
      → yo'q: "📢 Testni boshlash uchun kanalga qayta a'zo bo'ling"
1. purchases da (user, AYNAN SHU test_id) chipta bormi + payment tasdiqlanganmi?
      → yo'q: "🔒 Bu test uchun kirish huquqi yo'q. Narxi: ... [💳 To'lov]"
2. hozir start_at ≤ now < deadline_at oralig'idami?
      → erta: "Hali boshlanmadi"
3. attempts da yozuv bormi?
      → bor: yangi urinish EMAS — davom ettiriladi
```

Tekshiruv test davomida **har javobda** ham takrorlanadi (callback soxtalashga qarshi).

**Kechikkanlar:** deadline hamma uchun 22:00. 20:25 da kirsa → `⚠️ 25 daq kechikdingiz. Qolgan: 95 daq [▶️ Baribir boshlash]`.

## 5. Exam Mode (imtihon sharoiti)

- **Faqat bitta umumiy taymer** — savolga alohida vaqt yo'q, pauza yo'q. Vaqt faqat serverda (`deadline_at`)
- Ogohlantirishlar: 30 / 10 / 5 daqiqa qolganda
- Savol ko'rinishi (`protect_content=True` — forward/saqlash bloklangan):

```
[🖼 RASM yoki 📝 matn]
📝 12/45 | ✅ Belgilangan: 8 | ⏳ 1:34:20
[ A ] [ ✅B ] [ C ] [ D ]
[ ⬅️ Oldingi ] [ ➡️ Keyingi ]
[ 🗺 Navigator ] [ 🏁 Yakunlash ]
```

- Javobni **istalgan payt o'zgartirish / bekor qilish** mumkin; savolni tashlab ketish mumkin
- **Ochiq savol (36–45):** `✍️ Javobni raqamda yozing (masalan: 12 yoki -3,5)`.
  Normalizatsiya: `3,5`=`3.5`; kalitda ko'p variant: `0.5|1/2`. Stiker/rasm rad etiladi
- **🗺 Navigator** — javob varaqasi: 45 tugmalik grid (`1✅ 2⬜ ... 36✍️ ...`), istalgan savolga sakrash
- Har javob **darhol DB ga** → internet uzilsa: qaytganda `[▶️ Davom etish]`, taymer to'xtamagan bo'ladi
- 🆕 Savollar tartibi **aralashtirilmaydi** — admin PDF/kalitda qanday tartibda kiritgan bo'lsa, hammaga AYNAN shu tartibda ko'rsatiladi. (Ko'chirishga qarshi asosiy himoya — `protect_content=True` + har javobning DB'da vaqt bilan qayd etilishi, bu orqali shubhali bir xil-vaqtli javoblar keyinchalik tekshirilishi mumkin)
- Test paytida boshqa menyular qulflanadi (middleware exam-lock)
- **🏁 Yakunlash** tasdiq bilan: `⚠️ 8 savol belgilanmagan, 42 daq bor. Rostdanmi? [Ha] [Davom]`

## 6. Natija (jonli — 22:05 dan keyin)

```
🏆 MOCK #5 NATIJANGIZ | 🎫 ID: 1047
📊 Ball: 61,2 / 75 | 🎖 Daraja: B+
🥇 Reyting: 500 tadan 84-o'rin | ✅ To'g'ri: 32/45
[🖼 Sertifikat PNG]
[ 📈 Savollar tahlili ] [ 🎥 Video yechim ] [ ✉️ Apellyatsiya ]
```

Kanalga ID bo'yicha anonim umumiy reyting chiqadi.

🆕 **Apellyatsiya:** `✉️` bosilsa o'quvchi savol raqami + izoh yozadi → adminga tushadi (III.8 admin qismida davomi).

## 7. Arxiv test

1. `📚 Arxiv testlar` → `Mock #3 — 8 000 so'm (jonlida 500 kishi)` — narx yana admin belgilagan
2. To'lov jarayoni xuddi jonlidagidek (chek → admin → chipta). Yangi ID yo'q
3. O'quvchi **qulay vaqtda** `▶️` bosadi → `deadline = now + duration` shaxsiy → Exam Mode to'liq
4. Natija **darhol** (savollar kalibrlangan, θ MLE bilan <1 soniya) + `"Jonlida 500 tadan 73-o'rin bo'lardingiz"`
5. Arxiv natija **reytingga kirmaydi** — kabinetda `🏋️ Mashq` belgisi bilan
6. 🆕 **Aniqlik ogohlantiruvi:** natija ekranida doim ko'rinadi: `ℹ️ Bu mashq rejimi — ball jonli sinovda kalibrlangan qiyinlik darajalari asosida taxminiy hisoblanadi, rasmiy natija emas.` Shu bilan foydalanuvchi buni haqiqiy reyting emas, mashq sifatida qabul qiladi
7. 🆕 **Apellyatsiyadan keyin izchillik:** agar shu `test_id` bo'yicha keyinchalik kalit tuzatilsa yoki savol chiqarilsa (IV.5), yangi `b_difficulty` bilan **shu testni avval arxivda yechgan barcha urinishlar ham avtomatik qayta hisoblanadi** (MLE tez, <1s/kishi) va o'zgargan bo'lsa o'quvchiga xabar boradi: `"⚠️ Mock #3 kaliti tuzatildi, yangi ballingiz: ..."`. Shu orqali arxiv natijalari hech qachon eskirib qolmaydi

## 8. Kabinet

```
👤 Aliyev Vali | 🎫 ID: 1047
📊 3 jonli, 2 arxiv | 📈 Dinamika: 54 → 58 → 61,2
🎖 Eng yaxshi: B+ (61,2)
```

---

# IV QISM. ADMIN TOMONI — BOSHIDAN OXIRIGACHA

Faqat `.env` → `ADMIN_IDS` dagilar. Har harakat `admin_log` ga yoziladi.

## 1. Panel

```
👨‍💼 ADMIN PANEL
[ ➕ Yangi test ]       [ 📋 Testlar ]
[ 💳 To'lovlar (3🔔) ]  [ ✉️ Apellyatsiyalar (1🔔) ]
[ 📊 Statistika ]       [ 📢 E'lon yuborish ]
```

## 2. Test yaratish — PDF usuli (asosiy)

```
1) Nomi:        Mock #5 — Matematika
2) Savollar:    35 yopiq / 10 ochiq
3) Davomiylik:  120 daqiqa
4) 💰 Narx:     15 000        ← HAR TEST uchun alohida, admin o'zi belgilaydi
5) 📄 PDF yuboring (QOIDA: 1 savol = 1 sahifa!)
   → PyMuPDF: 45 sahifa → 45 PNG (dpi=200) → `media/tests/{test_id}/` papkaga
     saqlanadi (🆕 asl fayl zaxirasi) + Telegram'ga yuborilib `file_id` keshlanadi
     (tezkor yuborish uchun). `file_id` yaroqsiz bo'lib qolsa (token almashishi va h.k.)
     diskdagi asl PNG'dan qayta yuklanadi
   → "✅ 45 sahifa topildi. 45 savol sifatida saqlaymi? [Ha]"
6) 🔑 Kalit:    1-A 2-C ... 35-D  36:12 37:-4.5 38:0.5|1/2 ... 45:7
   → parse + "45/45 javob topildi ✅"
7) 👁 Preview — o'quvchi ko'radigan ko'rinishda; xato bo'lsa
   [✏️ N-savolni tahrirlash] → qo'lda: matn yoki yangi rasm
8) ✅ Tasdiqlash
```

**Zaxira — bittalab kiritish:** `➕ Savol` → turi (📝/🖼/aralash) → kontent → variantlar → to'g'ri javob. Tuzatish va kichik testlar uchun.

🆕 **Video yechim yuklash:** test yakunlangach admin `📋 Testlar → Mock #5 → 🎥 Video qo'shish` orqali havola (YouTube/kanal post) kiritadi → `tests.video_url` → o'quvchilarga `🎥` tugmasi faollashadi va xabar yuboriladi.

## 3. Rejim, vaqt, avtopilot

```
Rejim: [🔴 Jonli] [📚 Arxiv]
Jonli → vaqt: 12.02 20:00 (Asia/Tashkent)
✅ Rejalashtirildi [📢 Kanalga e'lon]
```

Tasdiqlashda APScheduler'ga 4 vazifa:

```python
scheduler.add_job(send_reminder, run_date=start - 30min)    # 19:30
scheduler.add_job(open_test,     run_date=start)            # 20:00 (+to'lov yopilishi)
scheduler.add_job(close_test,    run_date=deadline)         # 22:00
scheduler.add_job(run_rasch,     run_date=deadline + 5min)  # 22:05
```

🆕 **Restart himoyasi:** bot qayta ishga tushsa, scheduler vazifalari `tests` jadvalidan qayta tiklanadi (joblar xotirada emas, boshlang'ich manba — baza).

🆕 **Testni ko'chirish/bekor qilish:** `📋 Testlar → Mock #5 → [🕐 Vaqtni o'zgartirish] [🚫 Bekor qilish]`. Bekor qilinsa: status=`bekor_qilingan`, barcha chiptali o'quvchilarga xabar + chiptalari admin tanloviga ko'ra keyingi mockka ko'chiriladi yoki pul qaytariladi (qo'lda).

## 4. To'lovlar paneli

- Har chek → push + navbat. Ko'rsatiladi: chek, ism, telefon, **qaysi test, kutilgan summa**, 🆕/🔁 belgisi, 🆕 dublikat-chek ogohlantirishi
- `✅` → tranzaksiya (status + ID kerak bo'lsa + chipta + log + xabar)
- `❌` → sabab → xabar
- 20:00 da jonli test to'lovi avto-yopiladi

## 5. 🆕 Apellyatsiya va qayta hisoblash

Eng real stsenariy: kalitda xato ketdi yoki savol nosoz (Rasch misfit ham ko'rsatadi).

```
✉️ APELLYATSIYA #7 | ID: 1047 | Mock #5, 23-savol
"Javob kalitda B, lekin to'g'risi C bo'lishi kerak, mana isbot..."
[ 🔧 Kalitni tuzatish ] [ 🗑 Savolni chiqarish ] [ ❌ Rad etish ]
```

- **🔧 Kalitni tuzatish** → `correct_answer` yangilanadi → Rasch **avto qayta hisoblanadi** (jonli JMLE + shu testning barcha arxiv urinishlari MLE bilan, III.7-band 7) → o'zgargan natijalar qayta yuboriladi (`"⚠️ 23-savol kaliti tuzatildi, yangi ball: ..."`)
- **🗑 Savolni chiqarish** → `is_excluded=TRUE` → test 44 savol bo'yicha qayta kalibrlanadi (jonli + arxiv, xuddi yuqoridagidek)
- Hammasi `admin_log` da qoladi

## 6. Statistika

- Test: ishtirokchilar, o'rtacha ball, darajalar taqsimoti
- Savol: b qiyinlik, % to'g'ri, **misfit ro'yxati** (sifatsiz savollar signali)
- Moliya: tushum test kesimida, tasdiqlangan/rad etilgan
- 🆕 Umumiy: userlar soni, bloklaganlar, konversiya (ro'yxat → to'lov)

## 7. 📢 Broadcast

Admin matn/rasm yuboradi → `outbox` navbatiga → 25 msg/s bilan tarqatiladi → hisobot: `✅ 480 yetdi, 🚫 20 bloklagan`.

---

# V QISM. RASCH ENGINE

**Jonli (22:05):** javob matritsasi (N×45, `is_excluded` chiqarib) → **JMLE** iteratsiya → `b_difficulty` savollarga, `theta` o'quvchilarga → logit → **75-shkala** → daraja → reyting → `calibrated=TRUE`.

**Arxiv (darhol):** b lar tayyor → bitta o'quvchi uchun **MLE** (Newton–Raphson, <1 s) → ball → jonli bilan taqqoslash.

**Chekka holatlar:**
- 0% yoki 100% yechilgan savollar kalibrlashdan chiqariladi
- Hammasiga to'g'ri/noto'g'ri javob berganlarga θ chegaralab beriladi
- 🆕 **Minimal ishtirokchi qoidasi:** jonli testda **50 tadan kam** ishtirokchi bo'lsa, JMLE ishonchsiz — bot avtomatik klassik % ballga o'tadi va natijada halol yozadi: `"Ishtirokchilar kam bo'lgani uchun bu test klassik usulda baholandi"`. 50+ bo'lsa Rasch
- 🆕 **Yaxlitlash qoidasi:** daraja (A+/A/B+/...) belgilashdan oldin `ball_75` har doim **1 xonagacha yaxlitlanadi** (`round(ball_75, 1)`) — float hisoblash xatoligi (masalan 64.999999 ≠ 65.0) chegara darajasini noto'g'ri belgilashining oldini olish uchun
- 🆕 **Teng ball (tie-break) qoidasi:** reytingda (`rank_position`) ball teng bo'lsa, avval `ball_75` kamayish tartibida, keyin `finished_at` o'sish tartibida (testni **tezroq tugatgan** yuqori o'rinda) saralanadi

> Eslatma: BBA rasmiy logit→ball koeffitsiyentlarini e'lon qilmagan; metodika aynan, natija rasmiyga juda yaqin, botda "norasmiy mock" deb ochiq yoziladi.

---

# VI QISM. XAVFSIZLIK VA ISHONCHLILIK (yakuniy jadval)

| Xavf | Yechim |
|---|---|
| Savollar tarqalishi | `protect_content=True`, savollar faqat test vaqtida |
| Ikki akkaunt | telefon (contact) + ID bog'lami, `UNIQUE(user,test)` urinish |
| Ko'chirish | savollar tartibi barchaga bir xil (admin kiritgan tartib), asosiy himoya `protect_content` + javob vaqtlari audit |
| Vaqtni aldash | vaqt faqat serverda, timezone-aware |
| Internet uzilishi | har javob darhol DB, `davom etish` |
| Birovning ID'si | ID qo'lda yozilmaydi — telegram_id avtomatik |
| Boshqa testga suqilish | chipta aniq `test_id` ga, baza `UNIQUE`, har javobda tekshiruv |
| Chek dublikati 🆕 | `receipt_hash` bo'yicha ogohlantirish |
| Kechikish adolatsizligi | deadline hamma uchun bir xil |
| Arxiv reytingni buzishi | arxiv natija reytingga kirmaydi |
| Bot restarti 🆕 | scheduler bazadan qayta tiklanadi |
| Telegram limiti 🆕 | outbox navbati, 25 msg/s |
| Admin xatosi 🆕 | admin_log audit + apellyatsiya/qayta hisoblash |
| Ma'lumot yo'qolishi 🆕 | kunlik `pg_dump` backup (cron), 7 kunlik saqlash |
| ID dublikati (2 admin bir vaqtda) 🆕 | Postgres SEQUENCE orqali atomik `public_id`, `MAX()+1` ishlatilmaydi |
| ID almashtirilishi 🆕 | `public_id` berilgach o'zgarmas (immutable), hech qanday admin amali orqali qayta yozilmaydi |
| Bitta chekni ikki admin qayta ishlashi 🆕 | atomik `UPDATE ... WHERE status='kutilmoqda'`, kim birinchi bossa shu qabul qilinadi |
| Chek bilan spam qilish 🆕 | bitta testga bitta `kutilmoqda` chek limiti |
| Arxiv natijasi eskirib qolishi (apellyatsiyadan keyin) 🆕 | kalit tuzatilsa/savol chiqarilsa, shu testning barcha arxiv urinishlari ham avtomatik qayta hisoblanadi |
| Chegara balida noto'g'ri daraja (float xatoligi) 🆕 | daraja belgilashdan oldin `ball_75` 1 xonagacha yaxlitlanadi |
| Reytingda teng ball nizosi 🆕 | tie-break: ball → keyin tezroq tugatgan yuqorida |
| Ro'yxatdan keyin kanaldan chiqib ketish 🆕 | a'zolik test boshlashda (`▶️`) qayta tekshiriladi |
| `file_id` yaroqsiz bo'lib qolishi 🆕 | savol PNG'lari diskda (`media/`) ham asl nusxada saqlanadi |

---

# VII QISM. LOYIHA STRUKTURASI

```
rasch_bot/
├── bot/
│   ├── main.py                  # start, dispatcher, scheduler tiklash
│   ├── config.py                # .env: TOKEN, ADMIN_IDS, DB, KARTA, KANAL, TZ
│   ├── handlers/
│   │   ├── user/
│   │   │   ├── registration.py  # /start, kontakt, viloyat, kanal tekshiruv
│   │   │   ├── payment.py       # to'lov, chek, dublikat tekshiruv
│   │   │   ├── exam.py          # Exam Mode, navigator, javoblar, yakunlash
│   │   │   ├── archive.py       # arxiv testlar
│   │   │   ├── cabinet.py       # kabinet, natijalar, tahlil
│   │   │   └── appeal.py        # 🆕 apellyatsiya yuborish
│   │   └── admin/
│   │       ├── test_create.py   # PDF, kalit, preview, narx, vaqt
│   │       ├── test_manage.py   # 🆕 ko'chirish, bekor qilish, video qo'shish
│   │       ├── payments.py      # tasdiqlash (ID berish shu yerda)
│   │       ├── appeals.py       # 🆕 kalit tuzatish, qayta hisoblash
│   │       ├── broadcast.py     # 🆕 e'lon (outbox orqali)
│   │       └── stats.py
│   ├── keyboards/               # navigator grid, menyu, admin tugmalar
│   ├── states/                  # FSM: registration, payment, exam, admin
│   └── middlewares/             # admin filtri, exam-lock, kanal-check
├── core/
│   ├── rasch.py                 # JMLE, MLE, 75-shkala, misfit
│   ├── pdf_parser.py            # PyMuPDF: PDF → PNG
│   ├── answer_key.py            # kalit parse, javob normalizatsiya
│   ├── certificate.py           # Pillow sertifikat
│   ├── scheduler.py             # 4 vazifa + restart tiklash
│   └── sender.py                # 🆕 outbox: 25 msg/s, is_blocked
├── db/
│   ├── models.py                # SQLAlchemy — 9 jadval
│   └── queries.py               # check_access va boshqalar
├── media/tests/{test_id}/       # 🆕 savol PNG'larining asl nusxasi (file_id zaxirasi)
├── scripts/backup.sh            # 🆕 kunlik pg_dump
├── .env
└── requirements.txt
```

---

# VIII QISM. ISHGA TUSHIRISH BOSQICHLARI

1. **MVP:** ro'yxat + kanal tekshiruv + to'lov/ID + PDF yuklash + jonli Exam Mode (navigator) + klassik ball
2. **Rasch:** JMLE + 75-shkala + daraja + reyting + avtopilot + min-50 qoidasi
3. **Mahsulot:** sertifikat PNG + video yechim + kanal reytingi + broadcast/outbox
4. **Kengaytma:** arxiv rejim (MLE) + kabinet + taqqoslash + apellyatsiya/qayta hisoblash
5. **Avtomatlashtirish:** Click/Payme API + web-admin (FastAPI) + boshqa fanlar
