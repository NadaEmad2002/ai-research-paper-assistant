"""
extraction.py
=============
مسؤول عن:
1. فتح ملف PDF واستخراج النص الخام منه صفحة بصفحة.
2. تنظيف النص (إزالة الهيدرز/الفوترز المكررة، أرقام الصفحات، الأسطر المكسورة).
3. تقسيم الورقة إلى أقسام منطقية (Abstract, Introduction, Related Work,
   Methodology, Results, Discussion, Conclusion, References) بالاعتماد على
   heuristics على العناوين (خط أكبر / bold / نمط نصي معروف).

نستخدم PyMuPDF (fitz) لأنه بيحافظ على معلومات الفونت والحجم لكل "span"،
وده بيدينا إشارة قوية على إن السطر ده "عنوان قسم" مش نص عادي.
"""

import re
import fitz  # PyMuPDF
from dataclasses import dataclass, field


# أسماء الأقسام الشائعة في أوراق الأبحاث (بالإنجليزي غالبًا، وممكن نضيف عربي لاحقًا)
KNOWN_SECTION_TITLES = [
    "abstract",
    "introduction",
    "related work",
    "background",
    "literature review",
    "methodology",
    "method",
    "materials and methods",
    "approach",
    "experiments",
    "experimental setup",
    "results",
    "results and discussion",
    "discussion",
    "evaluation",
    "conclusion",
    "conclusions",
    "future work",
    "acknowledgments",
    "acknowledgements",
    "references",
    "appendix",
]


@dataclass
class Section:
    title: str
    content: str = ""


@dataclass
class ExtractedPaper:
    raw_text: str
    sections: list = field(default_factory=list)  # list[Section]
    page_count: int = 0
    title_guess: str = ""


def _is_probable_heading(span_text: str, font_size: float, avg_body_size: float, flags: int) -> bool:
    """
    قرار إن كان السطر ده عنوان قسم أو لأ، بناءً على:
    - حجم الخط أكبر من متوسط النص العادي
    - أو bold (flags & 2**4 بيدل على bold في PyMuPDF)
    - ومطابقة (كاملة أو جزئية) لأسماء أقسام معروفة
    """
    text_clean = span_text.strip().lower().strip(":.").strip()
    if not text_clean or len(text_clean) > 60:
        return False

    is_bold = bool(flags & 2 ** 4)
    is_bigger = font_size > avg_body_size + 0.5

    # تطابق مباشر مع أسماء معروفة (أقوى إشارة)
    for known in KNOWN_SECTION_TITLES:
        if text_clean == known or text_clean.startswith(known):
            return True

    # نمط "1. Introduction" أو "I. Introduction" أو "1 Introduction"
    numbered_pattern = re.match(r"^([0-9]+|[ivxIVX]+)[\.\)]?\s+[A-Za-z].{2,40}$", span_text.strip())
    if numbered_pattern and (is_bold or is_bigger):
        return True

    return False


def extract_pdf(file_path: str) -> ExtractedPaper:
    doc = fitz.open(file_path)

    all_spans = []  # (text, font_size, flags, page_num)
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"]
                    if text.strip():
                        all_spans.append((text, span["size"], span["flags"], page_num))

    doc.close()

    if not all_spans:
        return ExtractedPaper(raw_text="", sections=[], page_count=0)

    # متوسط حجم الخط بيمثل "نص الجسم" العادي (body text)
    avg_body_size = sum(s[1] for s in all_spans) / len(all_spans)

    # أول سطر بخط كبير في أول صفحة غالبًا هو عنوان الورقة
    title_guess = ""
    for text, size, flags, page_num in all_spans:
        if page_num == 0 and size > avg_body_size + 3:
            title_guess += text.strip() + " "
        elif title_guess:
            break
    title_guess = title_guess.strip()

    # بناء الأقسام
    sections = []
    current_section = Section(title="Header")  # أي نص قبل أول عنوان معروف
    raw_text_parts = []

    for text, size, flags, page_num in all_spans:
        raw_text_parts.append(text)
        if _is_probable_heading(text, size, avg_body_size, flags):
            # اقفل القسم الحالي وابدأ قسم جديد
            if current_section.content.strip():
                sections.append(current_section)
            current_section = Section(title=text.strip())
        else:
            current_section.content += text + " "

    if current_section.content.strip():
        sections.append(current_section)

    # تنظيف بسيط: إزالة مسافات زايدة وأسطر مكسورة
    for sec in sections:
        sec.content = re.sub(r"\s+", " ", sec.content).strip()

    raw_text = re.sub(r"\s+", " ", " ".join(raw_text_parts)).strip()

    return ExtractedPaper(
        raw_text=raw_text,
        sections=sections,
        page_count=len(set(s[3] for s in all_spans)),
        title_guess=title_guess,
    )


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python extraction.py <path_to_pdf>")
        sys.exit(1)

    result = extract_pdf(sys.argv[1])
    print(f"Title guess: {result.title_guess}")
    print(f"Pages: {result.page_count}")
    print(f"Sections found: {[s.title for s in result.sections]}")
    print(f"\nFirst section preview:\n{result.sections[0].content[:300] if result.sections else 'N/A'}")
