"""
title_generator.py
===================
توليد عنوان مقترح للورقة اعتمادًا على الـ Abstract (أو أول جزء من النص لو
مفيش abstract واضح). مفيد في حالتين:
1. لو العنوان المستخرج من extraction.py طلع مش دقيق (مثلاً بسبب مشاكل تنسيق PDF)
2. لو المستخدم عايز عنوان مختصر/بديل بالعربي لورقة إنجليزية
"""

from llm_client import call_llm

MAX_INPUT_WORDS = 500


def _get_abstract_or_intro(sections) -> str:
    for section in sections:
        if "abstract" in section.title.lower():
            return section.content
    # لو مفيش abstract، خدي أول قسم فيه محتوى فعلي
    for section in sections:
        if section.title != "Header" and section.content.strip():
            return section.content
    return ""


def generate_title(sections, language: str = "ar") -> str:
    text = _get_abstract_or_intro(sections)
    words = text.split()
    text = " ".join(words[:MAX_INPUT_WORDS])

    system_prompt = (
        "أنت مساعد أكاديمي بتقترح عناوين دقيقة ومختصرة لأوراق بحثية بناءً على "
        "الملخص (Abstract) بتاعها."
    )
    lang_note = "اقترحي العنوان بالعربية." if language == "ar" else "Suggest the title in English."

    user_prompt = (
        f"{lang_note}\n"
        "اقترحي عنوانًا واحدًا دقيقًا ومختصرًا (أقل من 15 كلمة) لورقة بحثية بناءً "
        f"على الملخص التالي. رجعي العنوان فقط بدون أي شرح إضافي:\n\n{text}"
    )

    return call_llm(system_prompt, user_prompt, max_tokens=200)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from extraction import extract_pdf

    result = extract_pdf(sys.argv[1] if len(sys.argv) > 1 else "uploads/test_paper.pdf")
    print(f"العنوان المستخرج من الـ PDF: {result.title_guess}")
    print(f"العنوان المقترح من Claude: {generate_title(result.sections)}")
