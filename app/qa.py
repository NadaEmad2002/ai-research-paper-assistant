"""
qa.py
=====
الإجابة على أسئلة حرة عن الورقة (free-form Q&A) باستخدام أسلوب RAG مبسّط:

1. الـ chunks بتاعة الورقة (من chunking.py) بتتحول لـ TF-IDF vectors
   (بدل embedding model تقيل زي sentence-transformers — كافي جدًا لورقة
   واحدة وبيوفر وقت تحميل الموديل، وهو اختيار معماري كويس نناقشه في تقرير الكورس).
2. السؤال بييجي بنفس الـ TF-IDF space، وبنجيب أقرب k من الـ chunks (cosine similarity).
3. الـ chunks المسترجعة دي بتتبعت لـ Claude كـ context عشان يجاوب على السؤال
   بناءً عليها بس (مش من معرفته العامة) — ده بيقلل الـ hallucination.

الكلاس PaperIndex بيتبني مرة واحدة لكل ورقة (وقت الرفع)، وبعدين بيتسأل
عليه أكتر من مرة من غير ما نعيد بناء الـ TF-IDF في كل مرة.
"""

from dataclasses import dataclass
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from llm_client import call_llm


@dataclass
class RetrievedChunk:
    section_title: str
    text: str
    score: float


class PaperIndex:
    def __init__(self, chunks):
        """chunks: list[Chunk] من chunking.py"""
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(stop_words=None, ngram_range=(1, 2))
        texts = [c.text for c in chunks]
        if texts:
            self.matrix = self.vectorizer.fit_transform(texts)
        else:
            self.matrix = None

    def retrieve(self, question: str, top_k: int = 3) -> list:
        if self.matrix is None:
            return []
        query_vec = self.vectorizer.transform([question])
        scores = cosine_similarity(query_vec, self.matrix).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [
            RetrievedChunk(
                section_title=self.chunks[i].section_title,
                text=self.chunks[i].text,
                score=float(scores[i]),
            )
            for i in top_indices
            if scores[i] > 0  # نتجاهل chunks مالهاش أي تشابه لفظي مع السؤال
        ]


def answer_question(index: PaperIndex, question: str, language: str = "ar", top_k: int = 3) -> dict:
    """
    بيرجع dict فيه: answer, sources (أسماء الأقسام اللي اتسحبت منها الإجابة)
    """
    retrieved = index.retrieve(question, top_k=top_k)

    if not retrieved:
        no_context_msg = (
            "معنديش معلومات كافية في الورقة للإجابة على السؤال ده."
            if language == "ar"
            else "I don't have enough information in the paper to answer this question."
        )
        return {"answer": no_context_msg, "sources": []}

    context = "\n\n".join(f"[من قسم: {c.section_title}]\n{c.text}" for c in retrieved)

    system_prompt = (
        "أنت مساعد بيجاوب على أسئلة عن ورقة بحثية بناءً على مقتطفات (context) "
        "مسترجعة منها فقط. لو المقتطفات مش كافية للإجابة بدقة، قولي كده صراحة "
        "بدل ما تخترعي معلومات."
    )
    lang_note = "جاوبي بالعربية." if language == "ar" else "Answer in English."

    user_prompt = (
        f"{lang_note}\n\n"
        f"مقتطفات من الورقة:\n{context}\n\n"
        f"السؤال: {question}\n\n"
        "جاوبي بإيجاز ودقة بناءً على المقتطفات فقط."
    )

    answer = call_llm(system_prompt, user_prompt, max_tokens=800)
    sources = list({c.section_title for c in retrieved})

    return {"answer": answer, "sources": sources}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from extraction import extract_pdf
    from chunking import chunk_sections

    result = extract_pdf(sys.argv[1] if len(sys.argv) > 1 else "uploads/test_paper.pdf")
    chunks = chunk_sections(result.sections)
    index = PaperIndex(chunks)

    question = sys.argv[2] if len(sys.argv) > 2 else "إيه المنهجية المستخدمة في الورقة؟"
    result = answer_question(index, question)
    print(f"السؤال: {question}")
    print(f"الإجابة: {result['answer']}")
    print(f"المصادر: {result['sources']}")
