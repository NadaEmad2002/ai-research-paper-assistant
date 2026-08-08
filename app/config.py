"""
config.py
=========
إعدادات المشروع المركزية. بنقرأ من .env بدل ما نكرر os.environ.get في كل
ملف، وده بيسهّل التحكم في الإعدادات من مكان واحد.

المشروع بيستخدم Google Gemini API (مجاني بدون بطاقة ائتمان عبر Google AI
Studio) بدل Claude API، عشان يكون قابل للتشغيل من غير أي تكلفة.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# بندوّر على .env في مكانين: المجلد الرئيسي للمشروع (المكان الطبيعي، جنب
# README.md و requirements.txt) وجوه app/ (لو حد حطه هناك بالغلط). كده
# الإعداد بيشتغل بغض النظر عن المجلد اللي بتشغلي منه uvicorn.
_APP_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _APP_DIR.parent

for _candidate in (_PROJECT_ROOT / ".env", _APP_DIR / ".env"):
    if _candidate.exists():
        load_dotenv(dotenv_path=_candidate)
        break
else:
    load_dotenv()  # fallback: سلوك dotenv الافتراضي (بيدور في المجلد الحالي)


class Settings:
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    UPLOAD_DIR: str = os.environ.get("UPLOAD_DIR", "uploads")
    MAX_UPLOAD_SIZE_MB: int = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "20"))

    DEFAULT_LANGUAGE: str = os.environ.get("DEFAULT_LANGUAGE", "ar")

    CORS_ORIGINS: list = os.environ.get("CORS_ORIGINS", "*").split(",")

    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("paper_assistant")


logger = setup_logging()
