<div align="center">

# ⚡ اتومیشن اینستاگرام

**پنل مدیریت پاسخ خودکار به دایرکت‌ها و کامنت‌های اینستاگرام**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?style=flat-square&logo=render&logoColor=white)](https://render.com)

</div>

---

## ✨ امکانات

- 💬 **پاسخ خودکار به دایرکت** — بر اساس کلمه کلیدی، پیام دایرکت ارسال می‌شود
- 📝 **پاسخ خودکار به کامنت** — هم زیر کامنت (عمومی) هم دایرکت (خصوصی)
- 🔍 **جستجو و صفحه‌بندی** — مدیریت آسان قانون‌های متعدد
- 📊 **داشبورد** — آمار لحظه‌ای و دسترسی سریع
- 🔐 **سیستم لاگین** — احراز هویت با رمز عبور امن
- 😊 **Emoji Picker کامل** — انتخاب ایموجی از ۷ دسته‌بندی
- 🎨 **UI حرفه‌ای** — فونت وزیرماتن، تم تاریک، کاملاً RTL
- 📱 **Responsive** — سازگار با موبایل و دسکتاپ
- 🗄️ **دیتابیس SQLite** — بدون نیاز به سرویس خارجی
- 🚀 **آماده Deploy روی Render**

---

## 🖥️ پیش‌نیازها

- Python 3.10+
- حساب [Meta for Developers](https://developers.facebook.com/)
- اپلیکیشن اینستاگرام با دسترسی Instagram Messaging API

---

## 🚀 راه‌اندازی محلی

### ۱. Clone کردن پروژه

```bash
git clone https://github.com/your-username/ig-automation.git
cd ig-automation
```

### ۲. ساخت محیط مجازی

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
```

### ۳. نصب پکیج‌ها

```bash
pip install -r requirements.txt
```

### ۴. تنظیم متغیرهای محیطی

```bash
cp .env.example .env
```

فایل `.env` را باز کن و مقادیر را وارد کن:

```env
SECRET_KEY=a_very_long_random_secret_key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
```

### ۵. اجرا

```bash
python app.py
```

پنل در آدرس `http://127.0.0.1:5000` در دسترسه.

> **ورود پیش‌فرض:** نام کاربری و رمز از `.env` خوانده می‌شود.

---

## ☁️ Deploy روی Render

### ۱. Push کردن به GitHub

```bash
git add .
git commit -m "initial commit"
git push origin main
```

### ۲. ساخت سرویس در Render

1. وارد [render.com](https://render.com) شو
2. **New → Web Service** را انتخاب کن
3. ریپوزیتوری GitHub را وصل کن
4. تنظیمات زیر را وارد کن:

| فیلد | مقدار |
|------|-------|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |

### ۳. متغیرهای محیطی در Render

در پنل Render → **Environment Variables** این مقادیر را اضافه کن:

| کلید | توضیح |
|------|-------|
| `SECRET_KEY` | یک رشته تصادفی طولانی |
| `ADMIN_USERNAME` | نام کاربری ادمین |
| `ADMIN_PASSWORD` | رمز عبور ادمین |

### ۴. تنظیم Webhook در متا

بعد از Deploy، به **Meta for Developers** → اپلیکیشنت → **Webhooks** برو:

- **Callback URL:** `https://your-app.onrender.com/webhook`
- **Verify Token:** همان مقداری که در پنل تنظیمات وارد کردی

---

## 📁 ساختار پروژه

```
ig_app/
├── app.py                    # منطق اصلی Flask
├── requirements.txt          # پکیج‌های Python
├── render.yaml               # تنظیمات Deploy
├── .env.example              # نمونه متغیرهای محیطی
├── .gitignore
└── templates/
    ├── base.html             # Layout اصلی با Sidebar
    ├── login.html            # صفحه ورود
    ├── dashboard.html        # داشبورد
    ├── dm_rules.html         # لیست قانون‌های دایرکت
    ├── comment_rules.html    # لیست قانون‌های کامنت
    ├── dm_rule_form.html     # فرم ساخت/ویرایش دایرکت
    ├── comment_rule_form.html# فرم ساخت/ویرایش کامنت
    ├── settings.html         # تنظیمات
    └── change_password.html  # تغییر رمز عبور
```

---

## ⚙️ نحوه کار

```
کاربر پیام می‌فرستد
        ↓
Instagram → Meta Webhook
        ↓
/webhook (POST)
        ↓
بررسی قانون‌ها (trigger matching)
        ↓
ارسال پاسخ از طریق Graph API
```

### انواع تطبیق کلمه کلیدی

| نوع | توضیح | مثال |
|-----|-------|------|
| `contains` | پیام شامل کلمه باشد | `قیمت` در `قیمت محصول چنده؟` |
| `exact` | پیام دقیقاً برابر کلمه باشد | `سلام` == `سلام` |

---

## 🔒 امنیت

- رمزهای عبور با `SHA-256 + salt` هش می‌شوند
- توکن‌های اینستاگرام در دیتابیس ذخیره می‌شوند (نه کد)
- فایل `.env` در `.gitignore` قرار دارد
- تمام روت‌های UI با `@login_required` محافظت شده‌اند

---

## 🛠️ تکنولوژی‌ها

| ابزار | کاربرد |
|-------|--------|
| Flask | فریم‌ورک وب |
| Flask-SQLAlchemy | ORM دیتابیس |
| Flask-Login | مدیریت احراز هویت |
| SQLite | دیتابیس |
| Gunicorn | سرور production |
| Vazirmatn | فونت فارسی |
| Meta Graph API v21 | ارتباط با اینستاگرام |

---

<div align="center">

ساخته شده با ❤️ برای اتومیشن اینستاگرام

</div>
