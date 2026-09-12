# راه‌اندازی روی سرور شرکت (دیتابیس مشترک + اکتیودایرکتوری)

هدف: همه‌ی کارشناسان روی **یک دیتابیس واحد** کار کنند و با **اکانت دامنه‌ی خودشان** وارد شوند.

---

## ۱) چه سروری لازم است؟

برنامه یک اپلیکیشن دسکتاپ ویندوزی است؛ پس سرور فقط نقش **نگهدارنده‌ی دیتابیس** را دارد.

| مورد | پیشنهاد |
|---|---|
| سیستم‌عامل | **Windows Server 2019 یا 2022** (Standard) — عضو دامنه |
| نقش | فقط Database Server (نیازی به IIS یا وب نیست) |
| دیتابیس | **SQL Server 2019/2022 Express** — رایگان، تا ۱۰ گیگابایت، برای این حجم داده کاملاً کافی است |
| CPU / RAM | ۲ تا ۴ هسته، ۸ گیگ رم |
| دیسک | ۵۰ گیگ (دیتابیس این برنامه در سال به چند ده مگابایت هم نمی‌رسد) |
| بکاپ | Maintenance Plan روزانه + کپی روی شیر شبکه |

> اگر سرور فیزیکی جدا ندارید، می‌توانید SQL Express را روی همان سرور فایل/دامنه‌ی موجود نصب کنید. **توصیه نمی‌شود** دیتابیس را روی یک شیر شبکه (`\\server\share\database.sqlite`) بگذارید؛ SQLite روی شبکه با چند کاربر همزمان خراب می‌شود.

### گزینه‌ی جایگزین
اگر ترجیح می‌دهید اوپن‌سورس باشد: **PostgreSQL 16** روی همان Windows Server یا یک VM لینوکسی. برنامه هر دو را پشتیبانی می‌کند (فقط `db_url` فرق می‌کند).

---

## ۲) مراحل نصب روی سرور

### الف) نصب SQL Server Express
1. دانلود «SQL Server 2022 Express» → نصب نوع **Basic**.
2. در Configuration Manager:
   - **TCP/IP** را برای instance فعال کنید.
   - پورت ثابت **1433** را ست کنید (یا SQL Browser را روشن بگذارید).
   - سرویس SQL Server را restart کنید.
3. در فایروال ویندوز، پورت **1433/TCP** را برای شبکه‌ی داخلی باز کنید.

### ب) ساخت دیتابیس و دسترسی‌ها (با Windows Authentication)
در SQL Server Management Studio:

```sql
CREATE DATABASE ITServiceLog;
GO

-- یک گروه در اکتیودایرکتوری بسازید (مثلاً IT-ServiceLog-Users)
-- و همه‌ی کارشناسان IT و سایت را عضو آن کنید، سپس:
CREATE LOGIN [COMPANY\IT-ServiceLog-Users] FROM WINDOWS;
GO

USE ITServiceLog;
CREATE USER [COMPANY\IT-ServiceLog-Users] FOR LOGIN [COMPANY\IT-ServiceLog-Users];
ALTER ROLE db_datareader ADD MEMBER [COMPANY\IT-ServiceLog-Users];
ALTER ROLE db_datawriter ADD MEMBER [COMPANY\IT-ServiceLog-Users];
GO

-- فقط برای اولین اجرا (ساخت خودکار جدول‌ها) به یک حساب با دسترسی ddl_admin نیاز است:
-- ALTER ROLE db_ddladmin ADD MEMBER [COMPANY\IT-ServiceLog-Users];
```

> پیشنهاد: بار اول برنامه را با حساب مدیر (که `db_owner` است) اجرا کنید تا جدول‌ها ساخته شوند، بعد `db_ddladmin` را بردارید.

### ج) نصب درایور روی کلاینت‌ها
روی هر کامپیوتری که برنامه نصب می‌شود، **ODBC Driver 17 (یا 18) for SQL Server** باید نصب باشد (یک فایل کوچک از سایت مایکروسافت — قابل توزیع با Group Policy).

> **نکته‌ی مهم برای ساخت نسخه‌ی نصبی:** پیش از اجرای `build.ps1` باید در محیط build دستور
> `pip install pyodbc` را زده باشید، وگرنه کتابخانه داخل فایل exe قرار نمی‌گیرد و اتصال به
> SQL Server کار نخواهد کرد. (اگر فقط SQLite محلی لازم دارید، نیازی به این کار نیست.)

---

## ۳) پیکربندی برنامه روی کلاینت‌ها

کنار فایل اجرایی (`C:\Program Files\ITServiceLog\`) فایل `config.json` بسازید:

```json
{
  "db_url": "mssql+pyodbc://@SRV-APP\\SQLEXPRESS/ITServiceLog?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes",
  "ad": {
    "enabled": true,
    "domain": "company.local",
    "auto_create_users": true,
    "default_role": "Technician",
    "default_department": "IT"
  }
}
```

نمونه‌ی آماده در `config.example.json` کنار همین برنامه هست.

**مسیرهایی که برنامه دنبال این فایل می‌گردد (به ترتیب):**
1. مسیر متغیر محیطی `ITSERVICELOG_CONFIG`
2. کنار فایل اجرایی → `config.json`
3. `%PROGRAMDATA%\ITServiceLog\config.json`  ← **بهترین گزینه برای توزیع با Group Policy**
4. کنار سورس پروژه

می‌توانید به‌جای فایل، فقط متغیر محیطی `ITSERVICELOG_DB` را با آدرس اتصال ست کنید.

اگر هیچ‌کدام نباشد، برنامه دقیقاً مثل قبل روی SQLite محلی کار می‌کند — پس نصب‌های فعلی بدون تغییر ادامه می‌دهند.

---

## ۴) ورود با اکتیودایرکتوری

با `"ad": { "enabled": true }`:

- کاربر **نام کاربری و رمز ویندوز خودش** را در صفحه‌ی ورود می‌زند (فرمت‌های `user`، `COMPANY\user` و `user@company.local` هر سه قبول است).
- اعتبارسنجی با `LogonUser` ویندوز انجام می‌شود (روی سیستم غیرویندوزی، اگر `ldap3` نصب باشد از LDAP استفاده می‌کند). **رمز عبور هیچ‌جا در برنامه ذخیره نمی‌شود.**
- اگر کاربر اولین بار وارد شود و `auto_create_users` روشن باشد، رکوردش خودکار ساخته می‌شود؛ بعد مدیر در تب «مدیریت کاربران» **نقش** و **بخش** (IT / سایت / هر دو) را برایش تنظیم می‌کند.
- حساب `admin` محلی همچنان کار می‌کند (به‌عنوان راه ورود اضطراری وقتی دامنه در دسترس نیست). **رمز پیش‌فرض `admin` را حتماً عوض کنید.**

---

## ۵) انتقال داده‌های فعلی به سرور

داده‌های موجود در `%APPDATA%\ITServiceLog\database.sqlite` است. برای انتقال:

1. برنامه را یک‌بار با `config.json` اجرا کنید تا جدول‌های خالی روی SQL Server ساخته شوند.
2. با ابزار **SQL Server Import and Export Wizard** (یا DBeaver) جدول‌ها را از فایل SQLite به SQL Server کپی کنید — به ترتیب:
   `technicians` → `systems` → `employees` → `tasks` → `service_records` → `service_record_tasks`
3. بعد از انتقال، مقدار `IDENTITY` هر جدول را بررسی کنید (`DBCC CHECKIDENT`).

> برنامه هنگام بالا آمدن، ستون‌های جدید نسخه‌ها را **خودکار** به دیتابیس موجود اضافه می‌کند؛ پس دیتابیس قدیمی شما بدون از دست رفتن داده به‌روز می‌شود.

---

## ۶) چک‌لیست نهایی

- [ ] SQL Express نصب، TCP/IP فعال، پورت ۱۴۳۳ در فایروال باز
- [ ] دیتابیس `ITServiceLog` ساخته شده و گروه AD دسترسی خواندن/نوشتن دارد
- [ ] ODBC Driver روی کلاینت‌ها نصب است
- [ ] `config.json` روی کلاینت‌ها (ترجیحاً از طریق GPO در `%PROGRAMDATA%`)
- [ ] بکاپ روزانه‌ی دیتابیس فعال است
- [ ] رمز حساب `admin` عوض شده است
- [ ] بخش هر کاربر (IT / سایت / هر دو) در «مدیریت کاربران» تنظیم شده است
