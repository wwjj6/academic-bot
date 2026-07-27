# 🚀 نشر البوت على Render.com (استضافة مجانية دائمة على الإنترنت)

هذا الدليل يشرح **خطوة بخطوة** كيف تجعل بوت المسابقات الأكاديمية يعمل بشكل دائم على الإنترنت
عبر منصة **Render.com** المجانية — بلا الحاجة لإبقاء جهازك يعمل، وبلا VPN
(لأن خادم Render يقع خارج الشبكة المحجوبة فيصل إلى تيليجرام مباشرة).

> ملخّص سريع: بوتك يعمل بنظام **polling**، وRender المجاني لا يوفّر إلا **Web Service**
> (يتطلّب فتح منفذ + ينام عند الخمول). لذلك أضفنا في الكود **خادم صحة صغيرًا**،
> وسنستخدم **UptimeRobot** لإبقائه مستيقظًا 24/7.

---

## 📋 الروابط التي ستحتاجها

| الغرض | الرابط |
|---|---|
| مستودع GitHub الخاص بك | https://github.com/hazeemcs/Telegram_bot |
| صفحة إنشاء خدمة جديدة في Render | https://dashboard.render.com/web/new?onboarding=active |
| لوحة تحكم Render | https://dashboard.render.com |
| UptimeRobot (لإبقاء الخدمة حيّة) | https://uptimerobot.com |
| معرفة رقم معرّفك في تيليجرام (@userinfobot) | https://t.me/userinfobot |
| الحصول على توكن البوت / إعادة توليده (@BotFather) | https://t.me/BotFather |
| توثيق Render حول الخطة المجانية | https://render.com/docs/free |

---

## 🧩 الخطوة 0: ما الذي تغيّر في الكود (تمّ مسبقًا)

لكي يعمل البوت على الاستضافة السحابية، أُجري تعديلان (وهما لا يؤثران على تشغيلك المحلي إطلاقًا):

1. **`utils/helpers.py`** — صار يقرأ الإعدادات بهذا الترتيب:
   `config.example.json` (افتراضيات) ← ثم `config.json` (محليًا) ← ثم **متغيرات البيئة** (على Render).
   أي أنّ التوكن على Render يُقرأ من متغير البيئة `BOT_TOKEN` بدلًا من `config.json`
   (الذي لا يُرفع إلى GitHub لأسباب أمنية).

2. **`bot.py`** — أُضيف **خادم HTTP خفيف** (`start_health_server`) يفتح المنفذ الذي يطلبه Render.
   يعمل **فقط** عند وجود متغير البيئة `PORT` (الذي يضبطه Render تلقائيًا)، ويردّ `Academic bot is running`.
   هذا يمنع فشل النشر بسبب «عدم اكتشاف منفذ مفتوح»، ويُستخدم كنقطة يفحصها UptimeRobot.

> إن كنت قد نفّذت الخطوة 1 (رفع التعديلات) مسبقًا، تجاوز إلى الخطوة 2.

---

## 📤 الخطوة 1: رفع التعديلات إلى GitHub

Render يسحب الكود من GitHub، لذا يجب رفع التعديلات أولًا. افتح موجّه الأوامر داخل مجلد المشروع ونفّذ:

```bash
git add bot.py utils/helpers.py
git commit -m "Add cloud-hosting support (env config + health server for Render)"
git push
```

تأكّد أن الدفع تمّ بنجاح بزيارة: https://github.com/hazeemcs/Telegram_bot

> ⚠️ لا ترفع `config.json` (فيه التوكن) — وهو أصلًا مُستثنى في `.gitignore`. اتركه كما هو.

---

## 🌐 الخطوة 2: إنشاء الخدمة في Render

1. افتح صفحة إنشاء خدمة جديدة: https://dashboard.render.com/web/new?onboarding=active
2. في قسم **Source Code**: اختر **GitHub**، وامنح Render صلاحية الوصول، ثم اختر المستودع
   **`hazeemcs/Telegram_bot`** واضغط **Connect**.
3. املأ الحقول بالقيم التالية بالضبط:

| الحقل | القيمة |
|---|---|
| **Name** | `telegram-academic-bot` *(يصبح جزءًا من رابط الخدمة — يمكنك اختيار أي اسم)* |
| **Language** | `Python 3` |
| **Branch** | `main` |
| **Region** | `Frankfurt (EU Central)` *(الأقرب — أو أي منطقة)* |
| **Root Directory** | *(اتركه فارغًا)* |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python bot.py` |
| **Instance Type** | **Free** |

> ⚠️ لا تضغط **Create** بعد — أضِف متغيرات البيئة أولًا (الخطوة 3).

---

## 🔑 الخطوة 3: إضافة متغيرات البيئة (Environment Variables)

انزل إلى قسم **Environment Variables** واضغط **Add Environment Variable** لكل صفّ:

| Key (المفتاح) | Value (القيمة) |
|---|---|
| `BOT_TOKEN` | **توكن بوتك** — انسخه من ملف `config.json` (حقل `bot_token`)، أو أعِد توليده من @BotFather |
| `ADMIN_IDS` | **رقم معرّفك في تيليجرام** — احصل عليه من @userinfobot (مثال: `700123456`) |
| `ADMIN_USERNAMES` | `Hiam_Adnan,ElianMuse,HlIWIl` |
| `TIMEZONE` | `Asia/Aden` |
| `PYTHON_VERSION` | `3.12.7` |
| `PYTHONUNBUFFERED` | `1` |

ملاحظات:
- يمكن وضع أكثر من رقم/اسم مفصولًا بفاصلة، مثل: `ADMIN_IDS = 700123456, 800987654`.
- `ADMIN_USERNAMES` وحدها تكفي لصلاحيات الإشراف إن كان اسم مستخدمك ضمنها، لكن يُفضّل إضافة `ADMIN_IDS` أيضًا.
- **لا تشارك التوكن مع أحد.** لو تسرّب، أعِد توليده فورًا من @BotFather ثم حدّث `BOT_TOKEN` هنا.

بعد إضافة كل المتغيّرات، اضغط **Create Web Service**.

---

## 📜 الخطوة 4: متابعة الإقلاع والتأكد من العمل

1. ستنتقل تلقائيًا إلى صفحة الخدمة، وسيبدأ Render بتنفيذ **Build** ثم **Deploy**.
2. افتح تبويب **Logs** وانتظر حتى ترى هذه الأسطر (تعني النجاح):
   ```
   ✅ قاعدة البيانات جاهزة.
   🌐 خادم الصحة يعمل على المنفذ ... (وضع الاستضافة السحابية).
   🚀 بوت المسابقات الأكاديمية يعمل الآن...
   Application started
   ```
3. جرّب البوت في تيليجرام: أرسل `/start` — يجب أن يستجيب.
4. انسخ **رابط الخدمة** من أعلى الصفحة، سيكون بالشكل:
   `https://telegram-academic-bot.onrender.com`
   (ستحتاجه في الخطوة 5).

---

## ♾️ الخطوة 5: إبقاء البوت حيًّا 24/7 (خطوة إلزامية)

الخطة المجانية في Render **تُنيم الخدمة بعد ~15 دقيقة من الخمول**، وبما أن البوت لا يستقبل
زيارات HTTP فسينام ويتوقف عن العمل. لمنع ذلك، نجعل خدمة خارجية «تنبّهه» دوريًا:

1. أنشئ حسابًا مجانيًا على **UptimeRobot**: https://uptimerobot.com
2. اضغط **+ Add New Monitor**.
3. اضبط الخيارات التالية:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Telegram Academic Bot`
   - **URL (or IP)**: ألصق رابط خدمتك، مثل `https://telegram-academic-bot.onrender.com`
   - **Monitoring Interval**: `5 minutes` (كل 5 دقائق)
4. اضغط **Create Monitor**.

الآن سيبقى البوت مستيقظًا على مدار الساعة. ✅

---

## 🚫 القاعدة الذهبية: نسخة واحدة فقط

لا تُشغّل البوت بأكثر من مكان في الوقت نفسه — تشغيل نسختين بنفس التوكن يسبّب خطأ
`Conflict: terminated by other getUpdates request` (خطأ 409).

لذلك بعد النشر على Render، **أوقف** أي تشغيل محلي:
- `service\run_bot_forever.bat`
- أو المهمة المجدولة `TelegramAcademicBot` (شغّل `service\uninstall_bot_task.bat`)
- أو أي نافذة يعمل فيها `python bot.py`

اختر Render **فقط**.

---

## ⚠️ تنبيه مهم: قاعدة البيانات مؤقتة على الخطة المجانية

قرص Render المجاني **مؤقت (ephemeral)**: ملف `academic_bot.db` (قاعدة بيانات SQLite)
**يُمسح مع كل إعادة نشر أو إعادة تشغيل للخدمة** → تُفقد بيانات الطلاب والنقاط والمسابقات.

البوت سيعمل بشكل صحيح، لكن **بياناته لن تدوم** على الخطة المجانية. للحصول على بيانات دائمة تحتاج أحد الخيارين:
- **قرص Render دائم (Persistent Disk)** — ميزة مدفوعة.
- **قاعدة بيانات خارجية مجانية** مثل:
  - Neon (Postgres مجاني): https://neon.tech
  - Supabase (Postgres مجاني): https://supabase.com

  وهذا يتطلّب تعديلًا في كود قاعدة البيانات (`database/db.py`) للانتقال من SQLite إلى Postgres.

---

## 🛠️ حل المشكلات الشائعة

| العَرَض في السجل / السلوك | السبب والحل |
|---|---|
| `FileNotFoundError: config.json` | لم تُرفع تعديلات الكود. أعِد الخطوة 1 (git push)، وتأكّد أن `BOT_TOKEN` مضبوط. |
| `⚠️ ضع توكن البوت في config.json أولاً` | متغير البيئة `BOT_TOKEN` غير مضبوط أو خاطئ. راجع الخطوة 3. |
| `Port scan timeout reached, no open ports detected` | تعديل `bot.py` (خادم الصحة) لم يُرفع. أعِد الخطوة 1. |
| `telegram.error.Conflict ... 409` | هناك نسخة أخرى تعمل. راجع «القاعدة الذهبية». |
| البوت يتوقف عن الرد بعد قليل | الخدمة نامت. تأكّد من إعداد UptimeRobot (الخطوة 5). |
| `ModuleNotFoundError` أثناء البناء | تأكّد أن **Build Command** هو `pip install -r requirements.txt`. |

---

## 🔄 تحديث البوت لاحقًا

أي تعديل تدفعه إلى فرع `main` على GitHub، سيعيد Render نشره تلقائيًا:

```bash
git add .
git commit -m "وصف التعديل"
git push
```

يمكنك أيضًا إعادة النشر يدويًا من لوحة Render عبر **Manual Deploy → Deploy latest commit**.
