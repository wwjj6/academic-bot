# ☁️ نشر البوت على Google Cloud (خادم e2-micro مجاني للأبد)

هذا الدليل يشرح **خطوة بخطوة** كيف تشغّل بوت المسابقات الأكاديمية على **خادم Linux حقيقي**
من الطبقة المجانية الدائمة في Google Cloud (**e2-micro Always Free**) — يعمل 24/7 بلا توقف،
بلا الحاجة لإبقاء جهازك يعمل، **وبلا VPN** (الخادم في أمريكا فيصل إلى تيليجرام مباشرة).

## ⭐ لماذا Google Cloud أفضل من Render المجاني؟

| الميزة | Render (مجاني) | Google Cloud e2-micro |
|---|:---:|:---:|
| يعمل 24/7 بلا نوم | ❌ (ينام) | ✅ |
| بياناتك (قاعدة البيانات) دائمة | ❌ (تُمسح) | ✅ (قرص ثابت) |
| يحتاج حيلة UptimeRobot | ✅ | ❌ (غير مطلوب) |
| خادم Linux كامل بصلاحيات جذر | ❌ | ✅ |
| مجاني للأبد | ⚠️ محدود | ✅ |

**الوحيد المطلوب:** بطاقة بنكية **للتحقق فقط** (لا يُخصم منها شيء ضمن Always Free)، وبعض خطوات لينكس البسيطة.

---

## 📋 الروابط التي ستحتاجها

| الغرض | الرابط |
|---|---|
| لوحة تحكم Google Cloud | https://console.cloud.google.com |
| صفحة إنشاء الأجهزة (VM instances) | https://console.cloud.google.com/compute/instances |
| تفاصيل الطبقة المجانية الدائمة | https://cloud.google.com/free/docs/free-cloud-features#compute |
| مستودع GitHub الخاص بك | https://github.com/hazeemcs/Telegram_bot |
| معرفة رقم معرّفك في تيليجرام (@userinfobot) | https://t.me/userinfobot |
| توكن البوت / إعادة توليده (@BotFather) | https://t.me/BotFather |

---

## ⚠️ قبل أن تبدأ: شرط «المجاني للأبد»

خادم **e2-micro** يكون مجانيًا **فقط** إذا أنشأته في إحدى هذه المناطق الأمريكية الثلاث:

- `us-west1` (Oregon)
- `us-central1` (Iowa)
- `us-east1` (South Carolina)

وبمواصفات: جهاز واحد `e2-micro`، وقرص قياسي (Standard persistent disk) بحجم **حتى 30 جيجابايت**.
أي منطقة أو نوع جهاز آخر = **ستُحاسَب عليه**. التزم بالقيم أدناه بالضبط.

---

## 🧩 الخطوة 0: تجهيز الكود (تمّ مسبقًا)

الكود يدعم قراءة الإعدادات من `config.json` **أو** من متغيّرات البيئة. على هذا الخادم سنستخدم
`config.json` (نُنشئه على الخادم، ولا يُرفع إلى GitHub لأسباب أمنية). لا حاجة لأي تعديل إضافي.

---

## 🟦 الخطوة 1: إنشاء حساب ومشروع وتفعيل الفوترة

1. افتح: https://console.cloud.google.com وسجّل الدخول بحساب Google.
2. من الأعلى، أنشئ مشروعًا جديدًا (**New Project**) وسمِّه مثلًا `telegram-bot`.
3. فعّل **الفوترة (Billing)** عند الطلب — أضف بطاقة بنكية **للتحقق فقط**.
   موارد Always Free لن تُخصم منها شيء طالما التزمت بالحدود (خطوة 2).

---

## 🖥️ الخطوة 2: إنشاء الخادم (VM) بمواصفات Always Free

1. افتح: https://console.cloud.google.com/compute/instances
2. إن طُلب، فعّل **Compute Engine API** (زر Enable) وانتظر دقيقة.
3. اضغط **Create Instance** واضبط الحقول:

| الحقل | القيمة |
|---|---|
| **Name** | `telegram-bot` |
| **Region** | `us-central1 (Iowa)` *(أو us-west1 / us-east1 — إحدى الثلاث فقط)* |
| **Zone** | `us-central1-a` *(أي منطقة فرعية)* |
| **Series** | `E2` |
| **Machine type** | `e2-micro` (2 vCPU، 1 GB) — **المجاني** |
| **Boot disk → OS** | `Ubuntu` |
| **Boot disk → Version** | `Ubuntu 22.04 LTS` |
| **Boot disk → Type/Size** | `Standard persistent disk` — `30 GB` |
| **Firewall** | اتركه بلا تأشير (البوت لا يحتاج منافذ واردة) |

4. اضغط **Create** وانتظر حتى يصبح الجهاز جاهزًا (أيقونة خضراء).

---

## 🔌 الخطوة 3: الاتصال بالخادم (SSH)

أسهل طريقة: في صفحة **VM instances**، بجانب `telegram-bot`، اضغط زر **SSH**.
ستُفتح نافذة طرفية (Terminal) في المتصفّح مباشرة — لا تحتاج إعداد مفاتيح.

كل الأوامر التالية تُكتب داخل هذه النافذة.

---

## 📦 الخطوة 4: تثبيت المتطلبات الأساسية

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git
```

---

## 📥 الخطوة 5: تنزيل المشروع من GitHub

> مستودعك **خاص (private)**، لذا سيطلب `git clone` مصادقة. استخدم رمز الوصول (PAT) الموجود
> في ملف `API_Token` عندك ككلمة مرور، أو ألصقه مباشرة في الرابط كما في الأمر التالي.

```bash
# استبدل YOUR_TOKEN برمز الوصول (PAT) الخاص بك
git clone https://YOUR_TOKEN@github.com/hazeemcs/Telegram_bot.git
cd Telegram_bot
```

> إن كان المستودع عامًا (public) يكفي: `git clone https://github.com/hazeemcs/Telegram_bot.git`

---

## 🧪 الخطوة 6: إنشاء البيئة الافتراضية وتثبيت المكتبات

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 🔑 الخطوة 7: إنشاء ملف الإعدادات على الخادم

`config.json` غير موجود في المستودع (لأسباب أمنية)، لذا ننشئه على الخادم:

```bash
cp config.example.json config.json
nano config.json
```

عدّل القيم التالية داخل المحرّر:
- `bot_token` → **توكن بوتك** (انسخه من `config.json` عندك محليًا، أو من @BotFather).
- `admin_ids` → **رقم معرّفك في تيليجرام** (من @userinfobot)، مثال: `[700123456]`.
- `admin_usernames` → `["Hiam_Adnan", "ElianMuse", "HlIWIl"]`.

احفظ واخرج: `Ctrl+O` ثم `Enter` ثم `Ctrl+X`.

---

## ▶️ الخطوة 8: تجربة التشغيل

```bash
python bot.py
```

يجب أن ترى:
```
✅ قاعدة البيانات جاهزة.
🚀 بوت المسابقات الأكاديمية يعمل الآن...
Application started
```

جرّب `/start` في تيليجرام للتأكد من الرد، ثم أوقف التجربة بـ `Ctrl+C`.

---

## ♾️ الخطوة 9: جعله يعمل دائمًا (systemd) — يبدأ تلقائيًا ويعيد التشغيل عند أي توقف

أنشئ خدمة النظام (الأمر التالي يملأ المسارات واسم المستخدم تلقائيًا):

```bash
sudo tee /etc/systemd/system/telegrambot.service > /dev/null <<EOF
[Unit]
Description=Telegram Academic Bot
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$HOME/Telegram_bot
ExecStart=$HOME/Telegram_bot/venv/bin/python bot.py
Restart=always
RestartSec=5
User=$USER

[Install]
WantedBy=multi-user.target
EOF
```

فعّل الخدمة وشغّلها:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now telegrambot
```

الآن البوت يعمل 24/7، ويبدأ تلقائيًا حتى بعد إعادة تشغيل الخادم، ويُعاد تشغيله إذا توقّف.

---

## 🔎 الخطوة 10: التحقق والأوامر المفيدة

| الغرض | الأمر |
|---|---|
| حالة البوت | `sudo systemctl status telegrambot` |
| متابعة السجل مباشرة | `journalctl -u telegrambot -f` |
| إيقاف البوت | `sudo systemctl stop telegrambot` |
| تشغيله | `sudo systemctl start telegrambot` |
| إيقاف البدء التلقائي | `sudo systemctl disable telegrambot` |

---

## 🚫 القاعدة الذهبية: نسخة واحدة فقط

بعد التشغيل على Google Cloud، **أوقف أي نسخة أخرى** بنفس التوكن (على حاسوبك المحلي أو Render)،
وإلا يظهر خطأ `Conflict ... 409`. اختر خادمًا واحدًا فقط.

---

## 💾 ميزة مهمة: بياناتك دائمة هنا

على عكس Render المجاني، قرص Google Cloud **دائم**. ملف `academic_bot.db` يبقى محفوظًا
عبر إعادة التشغيل والتحديثات — لا تُفقد بيانات الطلاب والنقاط والمسابقات.

نصيحة (نسخة احتياطية دورية): يمكنك نسخ قاعدة البيانات وقتما تشاء:
```bash
cp ~/Telegram_bot/academic_bot.db ~/backup_$(date +%F).db
```

---

## 🔄 تحديث البوت لاحقًا

عند تعديل الكود ورفعه إلى GitHub:

```bash
cd ~/Telegram_bot
git pull
source venv/bin/activate
pip install -r requirements.txt      # فقط إن تغيّرت المتطلبات
sudo systemctl restart telegrambot
```

---

## 💰 تنبيه الفوترة (مهم)

- أنشئ **جهازًا واحدًا فقط** من نوع `e2-micro` في إحدى المناطق الثلاث المجانية.
- لا تنشئ عناوين IP ثابتة إضافية ولا أقراصًا كبيرة ولا أجهزة أخرى — قد تُحاسَب عليها.
- راقب الاستهلاك من: https://console.cloud.google.com/billing
- يمكنك ضبط **تنبيه ميزانية (Budget Alert)** بقيمة 1$ ليصلك تنبيه لو تجاوزت المجاني.

---

## 🛠️ حل المشكلات الشائعة

| العَرَض | السبب والحل |
|---|---|
| `ModuleNotFoundError` عند التشغيل | لم تُفعّل البيئة الافتراضية أو لم تُثبّت المكتبات. أعِد الخطوة 6. |
| `⚠️ ضع توكن البوت في config.json` | `bot_token` فارغ أو placeholder. عدّل `config.json` (خطوة 7). |
| `Authentication failed` عند `git clone` | رمز الوصول (PAT) خاطئ أو منتهٍ، أو ليس له صلاحية قراءة المستودع. |
| `telegram.error.Conflict ... 409` | نسخة أخرى تعمل. راجع «القاعدة الذهبية». |
| الخدمة لا تعمل | نفّذ `journalctl -u telegrambot -e` لقراءة الخطأ، وتأكّد من صحة المسارات في ملف الخدمة. |
| بطء أو نفاد ذاكرة | e2-micro فيه 1GB فقط؛ كافٍ لهذا البوت. أوقف أي برامج أخرى على الخادم. |

---

تمّ. بعد إتمام هذه الخطوات سيعمل بوتك بشكل دائم ومجاني وآمن، مع بيانات محفوظة، وبلا حاجة إلى VPN.
