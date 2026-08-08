"""
summarization.py
=================
تلخيص ورقة بحثية بطريقتين:
1. summarize_paper: ملخص عام شامل للورقة كلها (executive summary)
2. summarize_sections: ملخص لكل قسم على حدة (مفيد لو عايزة تعرضي outline
   تفصيلي بدل ملخص واحد كبير)

بنستخدم أول ~6000 كلمة من نص الورقة كحد أقصى في البرومبت عشان نتجنب
تكاليف/حدود context window غير ضرورية لورقة بحثية عادية (10-15 صفحة).
"""

from llm_client import call_llm

MAX_INPUT_WORDS = 6000


def _truncate(text: str, max_words: int = MAX_INPUT_WORDS) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " ...[تم اختصار النص لتجاوزه الحد الأقصى]"


def summarize_paper(full_text: str, language: str = "ar") -> str:
    """ملخص تنفيذي شامل للورقة كلها."""
    system_prompt = (
        "أنت مساعد أكاديمي متخصص في تلخيص أوراق الأبحاث العلمية. "
        "مهمتك تلخيص الورقة بدقة، مع التركيز على: المشكلة البحثية، المنهجية، "
        "النتائج الرئيسية، والمساهمة العلمية. لا تخترعي معلومات غير موجودة في النص."
    )
    lang_instruction = "اكتبي الملخص بالعربية الفصحى الواضحة." if language == "ar" else "Write the summary in English."

    user_prompt = (
        f"{lang_instruction}\n\n"
        f"لخصي الورقة البحثية التالية في 150-200 كلمة، في فقرة واحدة متماسكة:\n\n"
        f"{_truncate(full_text)}"
    )
    return call_llm(system_prompt, user_prompt, max_tokens=1000)


def summarize_sections(sections, language: str = "ar") -> dict:
    """ملخص قصير (2-3 جمل) لكل قسم على حدة. بيرجع dict {section_title: summary}."""
    system_prompt = (
        "أنت مساعد أكاديمي متخصص في تلخيص أقسام الأوراق البحثية بإيجاز شديد "
        "مع الحفاظ على الدقة العلمية."
    )
    lang_instruction = "بالعربية." if language == "ar" else "in English."

    results = {}
    for section in sections:
        if section.title == "Header" or not section.content.strip():
            continue
        user_prompt = (
            f"لخصي القسم التالي (بعنوان '{section.title}') في 2-3 جمل فقط {lang_instruction}\n\n"
            f"{_truncate(section.content, max_words=1500)}"
        )
        results[section.title] = call_llm(system_prompt, user_prompt, max_tokens=350)

    return results


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from extraction import extract_pdf

    result = extract_pdf(sys.argv[1] if len(sys.argv) > 1 else "uploads/test_paper.pdf")
    print("=== ملخص عام ===")
    print(summarize_paper(result.raw_text))
    print("\n=== ملخص كل قسم ===")
    for title, summary in summarize_sections(result.sections).items():
        print(f"\n[{title}]\n{summary}")
