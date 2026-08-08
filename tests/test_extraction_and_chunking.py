"""
test_extraction_and_chunking.py
================================
اختبارات للأجزاء اللي مش محتاجة Claude API (استخراج + تقسيم)، عشان
تشتغل في أي CI pipeline من غير ما تحتاجي تحطي مفتاح فعلي.

تشغيل:
    cd app && pytest ../tests -v
"""

import os
import sys
import fitz
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from extraction import extract_pdf, Section
from chunking import chunk_sections, Chunk


@pytest.fixture(scope="module")
def sample_pdf_path(tmp_path_factory):
    """بيبني PDF بسيط في الميموري بنفس المنطق المستخدم وقت التطوير."""
    tmp_dir = tmp_path_factory.mktemp("pdfs")
    path = str(tmp_dir / "sample.pdf")

    doc = fitz.open()
    page = doc.new_page()
    y = 50

    def add_line(text, size, bold=False):
        nonlocal y
        page.insert_text((50, y), text, fontsize=size, fontname="helv" if not bold else "hebo")
        y += size + 8

    add_line("A Sample Paper Title For Testing", 18, bold=True)
    y += 10
    add_line("Abstract", 14, bold=True)
    add_line("This is a short abstract sentence for testing purposes only.", 10)
    y += 10
    add_line("1. Introduction", 14, bold=True)
    add_line("This introduction has two sentences. Here is the second one.", 10)
    y += 10
    add_line("2. Conclusion", 14, bold=True)
    add_line("This concludes the test paper with a final short sentence.", 10)

    doc.save(path)
    doc.close()
    return path


def test_extract_pdf_returns_text(sample_pdf_path):
    result = extract_pdf(sample_pdf_path)
    assert result.raw_text.strip() != ""
    assert result.page_count == 1


def test_extract_pdf_detects_known_sections(sample_pdf_path):
    result = extract_pdf(sample_pdf_path)
    titles = [s.title for s in result.sections]
    assert "Abstract" in titles
    assert any("Introduction" in t for t in titles)
    assert any("Conclusion" in t for t in titles)


def test_extract_pdf_title_guess_not_empty(sample_pdf_path):
    result = extract_pdf(sample_pdf_path)
    assert result.title_guess != ""


def test_extract_pdf_empty_file_handled(tmp_path):
    # PDF فاضي (صفحة بدون نص) لازم يترجع بدون exception، بس بنص فاضي
    empty_path = str(tmp_path / "empty.pdf")
    doc = fitz.open()
    doc.new_page()
    doc.save(empty_path)
    doc.close()

    result = extract_pdf(empty_path)
    assert result.raw_text == ""
    assert result.sections == []


def test_chunk_sections_produces_chunks(sample_pdf_path):
    result = extract_pdf(sample_pdf_path)
    chunks = chunk_sections(result.sections)
    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.text.strip() != "" for c in chunks)


def test_chunk_sections_skips_header(sample_pdf_path):
    result = extract_pdf(sample_pdf_path)
    chunks = chunk_sections(result.sections)
    assert all(c.section_title != "Header" for c in chunks)


def test_chunk_sections_respects_max_words():
    # نص واقعي بجمل قصيرة متعددة (مش كلمة واحدة مكررة بلا علامات ترقيم)
    # عشان نختبر الـ splitting في الحالة الشائعة الفعلية.
    sentence = "This is a normal length sentence used for testing purposes only. "
    long_content = sentence * 40  # حوالي 480 كلمة، جمل قصيرة وواضحة
    sections = [Section(title="Test Section", content=long_content)]
    chunks = chunk_sections(sections, max_words=100)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text.split()) <= 150  # هامش بسيط بسبب الـ overlap


def test_chunk_sections_handles_pathological_single_sentence():
    # حالة حافة: نص بلا علامات ترقيم كافية (جملة واحدة ضخمة جدًا).
    # مش المفروض يرمي exception، وكل chunk المفروض يتقسم فعليًا مش يفضل كتلة واحدة ضخمة.
    long_content = " ".join(["كلمة"] * 1000) + "."
    sections = [Section(title="Test Section", content=long_content)]
    chunks = chunk_sections(sections, max_words=100)
    assert len(chunks) > 1
    # كل chunk لازم يكون أصغر بكتير من النص الكامل (1000 كلمة)، حتى لو فيه overlap بسيط
    for c in chunks:
        assert len(c.text.split()) < 300
