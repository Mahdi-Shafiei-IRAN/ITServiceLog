"""احراز هویت کاربران: ابتدا اکتیودایرکتوری (در صورت فعال بودن)، سپس رمز محلی.

برای فعال کردن ورود با اکانت دامنه، در فایل config.json بنویسید:

    "ad": { "enabled": true, "domain": "company.local", "auto_create_users": true }

کاربر با همان نام کاربری و رمز ویندوزی خودش وارد می‌شود. اگر رکوردی در جدول
کارشناسان نداشته باشد و auto_create_users فعال باشد، رکورد ساخته می‌شود و مدیر
می‌تواند بعداً نقش و بخش او را تنظیم کند.
"""
from database import config
from database.models import Technician, DEPT_IT


class AuthError(Exception):
    pass


def _ad_bind(username, password, domain):
    """بررسی نام کاربری/رمز مقابل دامنه. True یعنی معتبر."""
    if not password:
        return False

    # روش اول: ویندوز (بدون نیاز به کتابخانه‌ی اضافه)
    try:
        import win32security
        LOGON32_LOGON_NETWORK = 3
        LOGON32_PROVIDER_DEFAULT = 0
        handle = win32security.LogonUser(
            username, domain or None, password,
            LOGON32_LOGON_NETWORK, LOGON32_PROVIDER_DEFAULT)
        if handle:
            handle.Close()
        return True
    except ImportError:
        pass
    except Exception:
        return False

    # روش دوم: LDAP (اگر ldap3 نصب باشد؛ مثلاً روی سیستم غیرویندوزی)
    try:
        from ldap3 import Server, Connection
        user_principal = f"{username}@{domain}" if domain else username
        conn = Connection(Server(domain or "localhost"), user=user_principal,
                          password=password, auto_bind=True)
        conn.unbind()
        return True
    except Exception:
        return False


def authenticate(db, username, password):
    """کاربر معتبر را برمی‌گرداند یا AuthError پرتاب می‌کند."""
    username = (username or "").strip()
    if not username:
        raise AuthError("نام کاربری را وارد کنید.")

    user = db.query(Technician).filter(Technician.username == username).first()
    ad = config.ad_config()

    if ad["enabled"]:
        # اجازه‌ی ورود با فرمت DOMAIN\user یا user@domain هم داده می‌شود
        bare = username.split("\\")[-1].split("@")[0]
        if _ad_bind(bare, password, ad["domain"]):
            if not user:
                user = db.query(Technician).filter(Technician.username == bare).first()
            if not user:
                if not ad["auto_create_users"]:
                    raise AuthError("حساب دامنه معتبر است اما در برنامه تعریف نشده؛ با مدیر تماس بگیرید.")
                user = Technician(
                    full_name=bare,
                    username=bare,
                    password_hash="",          # رمز در دامنه نگهداری می‌شود
                    role=ad["default_role"],
                    department=ad["default_department"] or DEPT_IT,
                    is_active=True,
                )
                db.add(user)
                db.commit()
            if not user.is_active:
                raise AuthError("حساب کاربری شما غیرفعال شده است.")
            return user
        # اگر دامنه قبول نکرد، به رمز محلی برمی‌گردیم (برای حساب admin اضطراری)

    if user and user.password_hash and user.password_hash == password:
        if not user.is_active:
            raise AuthError("حساب کاربری شما غیرفعال شده است.")
        return user

    raise AuthError("نام کاربری یا رمز عبور اشتباه است.")


def ad_enabled():
    return config.ad_config()["enabled"]
