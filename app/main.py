"""
main.py
=======
نقطة الدخول الرئيسية: FastAPI app بيوفر endpoints لكل وظيفة من وظائف
الـ AI Research Paper Assistant.

تشغيل السيرفر:
    cp .env.example .env   # واملي مفتاحك جوه .env
    pip install -r requirements.txt
    cd app
    uvicorn main:app --reload --port 8000

بعدها:
    - التوثيق التفاعلي: http://localhost:8000/docs
    - الواجهة التجريبية: http://localhost:8000/app
"""

import os
import shutil
import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings, logger
from extraction import extract_pdf
from chunking import chunk_sections
from summarization import summarize_paper, summarize_sections
from keywords import extract_keywords
from questions import generate_questions
from title_generator import generate_title
from qa import PaperIndex, answer_question
from llm_client import LLMConfigError, LLMRequestError

app = FastAPI(
    title="AI Research Paper Assistant",
    description="استخراج، تلخيص، وتحليل أوراق بحثية بالذكاء الاصطناعي",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# تخزين مؤقت في الميموري: paper_id -> {extracted, chunks, index}
# ملاحظة: كافي لمشروع كورس. في إنتاج حقيقي هيتحول لـ database + persistent storage
# (مع تحدي: الـ PaperIndex نفسه مش سهل تسريحه في DB عادي، هيحتاج vector store).
PAPERS_STORE = {}


# ---------- Exception handlers: بترجع رسائل عربية واضحة بدل traceback خام ----------

@app.exception_handler(LLMConfigError)
async def llm_config_error_handler(request: Request, exc: LLMConfigError):
    logger.error(f"LLM config error: {exc}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(LLMRequestError)
async def llm_request_error_handler(request: Request, exc: LLMRequestError):
    logger.error(f"LLM request error: {exc}")
    return JSONResponse(status_code=503, content={"detail": f"مشكلة مؤقتة في الاتصال بـ Gemini: {exc}"})


class AskRequest(BaseModel):
    paper_id: str
    question: str
    language: str = settings.DEFAULT_LANGUAGE


def _get_paper_or_404(paper_id: str) -> dict:
    paper = PAPERS_STORE.get(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="paper_id مش موجود. ارفعي الورقة أولاً عبر /upload")
    return paper


@app.post("/upload")
async def upload_paper(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="لازم يكون الملف بصيغة PDF")

    paper_id = str(uuid.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{paper_id}.pdf")

    size_bytes = 0
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    with open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size_bytes += len(chunk)
            if size_bytes > max_bytes:
                f.close()
                os.remove(file_path)
                raise HTTPException(
                    status_code=413,
                    detail=f"الملف أكبر من الحد المسموح ({settings.MAX_UPLOAD_SIZE_MB}MB)",
                )
            f.write(chunk)

    logger.info(f"تم رفع ملف جديد: {file.filename} ({size_bytes / 1024:.0f} KB) -> paper_id={paper_id}")

    try:
        extracted = extract_pdf(file_path)
    except Exception as e:
        os.remove(file_path)
        logger.error(f"فشل استخراج النص من {file.filename}: {e}")
        raise HTTPException(status_code=422, detail=f"فشل قراءة الـ PDF: {e}")

    if not extracted.raw_text.strip():
        os.remove(file_path)
        raise HTTPException(
            status_code=422,
            detail="مقدرناش نستخرج أي نص من الملف. ممكن يكون PDF ممسوح ضوئيًا (scanned) بدون OCR.",
        )

    chunks = chunk_sections(extracted.sections)
    index = PaperIndex(chunks)

    PAPERS_STORE[paper_id] = {
        "extracted": extracted,
        "chunks": chunks,
        "index": index,
        "file_path": file_path,
        "filename": file.filename,
    }

    return {
        "paper_id": paper_id,
        "title_guess": extracted.title_guess,
        "page_count": extracted.page_count,
        "sections": [s.title for s in extracted.sections],
    }


@app.get("/summarize/{paper_id}")
def summarize(paper_id: str, per_section: bool = False, language: str = settings.DEFAULT_LANGUAGE):
    paper = _get_paper_or_404(paper_id)
    if per_section:
        return summarize_sections(paper["extracted"].sections, language=language)
    return {"summary": summarize_paper(paper["extracted"].raw_text, language=language)}


@app.get("/keywords/{paper_id}")
def keywords(paper_id: str, n: int = 10, language: str = settings.DEFAULT_LANGUAGE):
    paper = _get_paper_or_404(paper_id)
    return {"keywords": extract_keywords(paper["extracted"].raw_text, n_keywords=n, language=language)}


@app.get("/questions/{paper_id}")
def questions(paper_id: str, n: int = 6, language: str = settings.DEFAULT_LANGUAGE):
    paper = _get_paper_or_404(paper_id)
    return {"questions": generate_questions(paper["extracted"].raw_text, n_questions=n, language=language)}


@app.get("/title/{paper_id}")
def title(paper_id: str, language: str = settings.DEFAULT_LANGUAGE):
    paper = _get_paper_or_404(paper_id)
    return {
        "extracted_title": paper["extracted"].title_guess,
        "suggested_title": generate_title(paper["extracted"].sections, language=language),
    }


@app.post("/ask")
def ask(request: AskRequest):
    paper = _get_paper_or_404(request.paper_id)
    return answer_question(paper["index"], request.question, language=request.language)


@app.delete("/paper/{paper_id}")
def delete_paper(paper_id: str):
    """حذف ورقة من الـ store وملفها من القرص (مفيد وقت التطوير/الاختبار)."""
    paper = _get_paper_or_404(paper_id)
    if os.path.exists(paper["file_path"]):
        os.remove(paper["file_path"])
    del PAPERS_STORE[paper_id]
    return {"deleted": paper_id}


@app.get("/health")
def health():
    return {"status": "ok", "papers_in_memory": len(PAPERS_STORE)}


# ---------- واجهة تجريبية بسيطة (static HTML) للعرض السريع في الكورس ----------
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/app", StaticFiles(directory=_static_dir, html=True), name="static")


@app.get("/")
def root():
    return {
        "message": "AI Research Paper Assistant API",
        "docs": "/docs",
        "demo_ui": "/app",
        "endpoints": [
            "/upload", "/summarize/{paper_id}", "/keywords/{paper_id}",
            "/questions/{paper_id}", "/title/{paper_id}", "/ask", "/health",
        ],
    }
