"""
llm_client.py
=============
طبقة موحدة للتعامل مع Google Gemini API، بحيث كل الموديولز التانية
(summarization, keywords, questions, title, qa) تنادي عليها بدل ما كل
واحدة تكرر كود الاتصال. Gemini اتخترت بدل Claude لأن عندها free tier
حقيقي (بدون بطاقة ائتمان) عبر Google AI Studio، مناسب لمشروع كورس.

بتشمل:
- قراءة الإعدادات من config.py بدل os.environ المباشر
- retry تلقائي (مع exponential backoff) عند أخطاء rate-limit أو انقطاع مؤقت
- exceptions مخصصة عشان الـ endpoints في main.py تقدر تتعامل معاها بشكل مناسب
"""

import time
import json
from google import genai
from google.genai import types, errors

from config import settings, logger

MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2

_client = None


class LLMConfigError(Exception):
    """المفتاح مش متظبط أو مش موجود."""


class LLMRequestError(Exception):
    """فشل النداء للـ API بعد كل محاولات الـ retry."""


def get_client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.GEMINI_API_KEY:
            raise LLMConfigError(
                "GEMINI_API_KEY مش موجود. أنشئي ملف .env من .env.example، "
                "واجيبي مفتاح مجاني من https://aistudio.google.com/app/apikey "
                "وحطيه في .env (مش محتاج بطاقة ائتمان)."
            )
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 1024, json_mode: bool = False) -> str:
    """نداء نصي بسيط، بيرجع النص كـ string، مع retry عند الأخطاء المؤقتة.
    لو json_mode=True، بنطلب من Gemini يضمن رد JSON صالح على مستوى الـ API نفسه
    (response_mime_type)، مش بس بتعليمات في الـ prompt.

    ملاحظة مهمة: gemini-2.5-flash بيستخدم "thinking" (تفكير داخلي) بشكل
    افتراضي، وده بياخد جزء من max_output_tokens قبل ما يوصل للرد النهائي،
    وده ممكن يخلي الرد يتقطع (خصوصًا في الردود القصيرة زي الكلمات المفتاحية).
    بنوقفه هنا (thinking_budget=0) لأن المهام دي كلها استخراج/تلخيص مباشر
    مش محتاج استدلال معقد، وده كمان بيوفر من حصة الـ free tier."""
    client = get_client()
    last_error = None

    config_kwargs = dict(
        system_instruction=system_prompt,
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            text = response.text
            if text is None:
                # ممكن يحصل لو الرد اتوقف بسبب safety filters أو الوصول لحد max_tokens
                # قبل ما يكتب أي نص فعلي
                raise LLMRequestError(
                    "Gemini رجع رد فاضي (ممكن بسبب safety filters أو max_tokens قليل جدًا)."
                )
            return text.strip()

        except errors.ClientError as e:
            # 429 = rate limit، غيرها من أخطاء الـ 4xx مش هتتحل بإعادة المحاولة
            if e.code == 429:
                last_error = e
                wait = BASE_BACKOFF_SECONDS * attempt
                logger.warning(f"Rate limit (429)، بحاول تاني بعد {wait}s (محاولة {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            logger.error(f"خطأ من Gemini API: {e.code} - {e.message}")
            raise LLMRequestError(f"خطأ من Gemini API: {e.message}") from e

        except errors.ServerError as e:
            last_error = e
            wait = BASE_BACKOFF_SECONDS * attempt
            logger.warning(f"مشكلة مؤقتة في سيرفر Gemini، بحاول تاني بعد {wait}s (محاولة {attempt}/{MAX_RETRIES})")
            time.sleep(wait)

    logger.error(f"فشل النداء بعد {MAX_RETRIES} محاولات: {last_error}")
    raise LLMRequestError(f"فشل الاتصال بـ Gemini بعد {MAX_RETRIES} محاولات: {last_error}")


def call_llm_json(system_prompt: str, user_prompt: str, max_tokens: int = 1024):
    """
    نداء بيطلب من الموديل يرجع JSON فقط (باستخدام response_mime_type على
    مستوى الـ API، وده أضمن بكتير من مجرد تعليمات نصية)، وبيعمل parsing تلقائي.
    لو فشل الـ parsing رغم كده (نادر)، بيحاول مرة واحدة تانية قبل ما يرمي error.
    """
    for attempt in range(2):
        raw = call_llm(system_prompt, user_prompt, max_tokens=max_tokens, json_mode=True)
        cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            if attempt == 0:
                logger.warning("رد الموديل مش JSON صالح رغم json_mode، بحاول مرة تانية")
                continue
            raise LLMRequestError(f"فشل تحويل رد الموديل إلى JSON بعد محاولتين: {e}\nالرد الخام: {raw[:500]}") from e
