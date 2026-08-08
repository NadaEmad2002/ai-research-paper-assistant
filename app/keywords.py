"""
keywords.py
===========
استخراج كلمات/عبارات مفتاحية (keywords/key phrases) من الورقة البحثية
باستخدام Claude، مع تصنيفها حسب النوع (موضوع عام، طريقة تقنية، مجال بحثي)
عشان تكون مفيدة أكاديميًا مش مجرد قائمة عشوائية.
"""

from llm_client import call_llm_json

MAX_INPUT_WORDS = 3000


def _truncate(text: str, max_words: int = MAX_INPUT_WORDS) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def extract_keywords(full_text: str, n_keywords: int = 10, language: str = "ar") -> list:
    """
    بيرجع list of dicts: [{"term": "...", "category": "..."}]
    category ممكن تكون: "topic" (موضوع)، "method" (طريقة/تقنية)، "domain" (مجال)
    """
    system_prompt = (
        "أنت أداة استخراج كلمات مفتاحية أكاديمية دقيقة. استخرجي فقط مصطلحات "
        "موجودة فعليًا أو مستنتجة مباشرة من النص، ولا تخترعي مصطلحات غير مرتبطة."
    )

    lang_note = "اجعلي قيمة 'term' بالعربية إن أمكن، وإلا اتركيها بالإنجليزية للمصطلحات التقنية." if language == "ar" else ""

    user_prompt = (
        f"استخرجي أهم {n_keywords} كلمات/عبارات مفتاحية من الورقة البحثية التالية. "
        f"{lang_note}\n"
        "رجعي JSON على شكل: "
        '[{"term": "...", "category": "topic|method|domain"}, ...]\n\n'
        f"نص الورقة:\n{_truncate(full_text)}"
    )

    return call_llm_json(system_prompt, user_prompt, max_tokens=1500)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from extraction import extract_pdf

    result = extract_pdf(sys.argv[1] if len(sys.argv) > 1 else "uploads/test_paper.pdf")
    for kw in extract_keywords(result.raw_text):
        print(f"- {kw['term']} ({kw['category']})")
