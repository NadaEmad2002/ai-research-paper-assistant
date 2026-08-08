"""
questions.py
============
توليد أسئلة مقترحة عن الورقة البحثية، بمستويات صعوبة مختلفة، عشان تفيد
طالب أو باحث بيراجع الورقة (comprehension check) أو حتى كـ starter
questions للـ Q&A module.
"""

from llm_client import call_llm_json

MAX_INPUT_WORDS = 4000


def _truncate(text: str, max_words: int = MAX_INPUT_WORDS) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def generate_questions(full_text: str, n_questions: int = 6, language: str = "ar") -> list:
    """
    بيرجع list of dicts: [{"question": "...", "difficulty": "easy|medium|hard"}]
    - easy: أسئلة فهم مباشر (إيه المشكلة؟ إيه المنهجية؟)
    - medium: أسئلة تحليلية (ليه استخدموا الطريقة دي؟)
    - hard: أسئلة نقدية (إيه القيود؟ ممكن تتطبق إزاي في سياق تاني؟)
    """
    system_prompt = (
        "أنت مساعد أكاديمي بيولّد أسئلة مراجعة عن أوراق بحثية لمساعدة القارئ "
        "على فهم واستيعاب المحتوى بعمق."
    )
    lang_note = "اكتبي الأسئلة بالعربية." if language == "ar" else "Write questions in English."

    user_prompt = (
        f"{lang_note}\n"
        f"اقترحي {n_questions} أسئلة عن الورقة البحثية التالية، بحيث يكون فيه توزيع "
        "متوازن بين المستويات: أسئلة فهم مباشر (easy)، أسئلة تحليلية (medium)، "
        "وأسئلة نقدية (hard).\n"
        'رجعي JSON على شكل: [{"question": "...", "difficulty": "easy|medium|hard"}, ...]\n\n'
        f"نص الورقة:\n{_truncate(full_text)}"
    )

    return call_llm_json(system_prompt, user_prompt, max_tokens=1800)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from extraction import extract_pdf

    result = extract_pdf(sys.argv[1] if len(sys.argv) > 1 else "uploads/test_paper.pdf")
    for q in generate_questions(result.raw_text):
        print(f"[{q['difficulty']}] {q['question']}")
