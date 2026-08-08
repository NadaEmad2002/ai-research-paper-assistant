"""
chunking.py
===========
تقسيم نص الورقة إلى chunks بحجم مناسب لاستخدامها في:
- التلخيص لو الورقة طويلة جدًا وتخطت context window
- الـ retrieval بتاع الـ Q&A (كل chunk بيتخزن مع رقم القسم اللي جاله منه)

الاستراتيجية: نبدأ من الأقسام اللي طلعت من extraction.py (لأنها منطقية أصلاً)،
ولو أي قسم أطول من الحد الأقصى بنقسمه على جمل مع overlap بسيط عشان محافظش
على السياق بين الأجزاء.
"""

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    id: int
    section_title: str
    text: str


def _split_into_sentences(text: str) -> list:
    # تقسيم بسيط على الجمل، بيراعي الاختصارات الشائعة زي "e.g." و "et al."
    text = re.sub(r"\b(e\.g|i\.e|et al|Fig|Eq|vs)\.\s", r"\1<DOT> ", text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.replace("<DOT>", ".") for s in sentences if s.strip()]


def chunk_sections(sections, max_words: int = 220, overlap_sentences: int = 1) -> list:
    """
    sections: list[Section] من extraction.py
    بيرجع list[Chunk]
    """
    chunks = []
    chunk_id = 0

    for section in sections:
        if section.title == "Header":
            continue  # ده غالبًا العنوان بس، مش محتوى فعلي

        sentences = []
        for s in _split_into_sentences(section.content):
            # حالة حافة: جملة واحدة أطول من الحد الأقصى (نص بعلامات ترقيم قليلة)
            # بنقسمها على كلمات عشان محدش chunk يطلع ضخم بشكل غير متوقع
            words = s.split()
            if len(words) > max_words:
                for i in range(0, len(words), max_words):
                    sentences.append(" ".join(words[i:i + max_words]))
            else:
                sentences.append(s)
        current_words = []
        current_sentences = []

        for sentence in sentences:
            sentence_word_count = len(sentence.split())
            current_word_count = sum(len(s.split()) for s in current_sentences)

            if current_word_count + sentence_word_count > max_words and current_sentences:
                chunks.append(
                    Chunk(id=chunk_id, section_title=section.title, text=" ".join(current_sentences))
                )
                chunk_id += 1
                # نبدأ الـ chunk الجديد بعدد overlap_sentences من آخر الـ chunk القديم
                current_sentences = current_sentences[-overlap_sentences:] if overlap_sentences else []

            current_sentences.append(sentence)

        if current_sentences:
            chunks.append(Chunk(id=chunk_id, section_title=section.title, text=" ".join(current_sentences)))
            chunk_id += 1

    return chunks


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from extraction import extract_pdf

    result = extract_pdf(sys.argv[1] if len(sys.argv) > 1 else "uploads/test_paper.pdf")
    chunks = chunk_sections(result.sections)
    for c in chunks:
        print(f"[{c.id}] ({c.section_title}) {c.text[:80]}...")
