

https://github.com/user-attachments/assets/68034322-861a-4bd8-b32e-72f6f73861ca



# AI Research Paper Assistant

An AI-powered tool that turns a research paper (PDF) into a structured, explorable summary: overall and per-section summaries, classified keywords, review questions, a suggested title, and grounded question-answering over the paper's own content.

Built as an NLP coursework project, with an emphasis on a complete text-processing pipeline — extraction, chunking, retrieval, and generation — rather than a thin wrapper around a single API call.

Powered by the **Google Gemini API**, which offers a genuine free tier through Google AI Studio with no credit card required, keeping the project fully runnable at zero cost.

---

## Features

- **PDF text extraction with automatic section detection** — Abstract, Introduction, Methodology, Results, Conclusion, etc., identified using font size and boldness, not just keyword matching.
- **Summarization** — an overall summary, or a concise summary per section.
- **Keyword extraction** — classified into topic / method / domain.
- **Review question generation** — tagged by difficulty (easy / medium / hard).
- **Title suggestion** — generated from the abstract.
- **Free-form Q&A** — a lightweight retrieval-augmented generation (RAG) pipeline that answers questions grounded in the paper's actual content.
- **Demo web interface** and full interactive API documentation (Swagger).

---

## Quick Start

### 1. Get a free API key (2 minutes)

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with any Google account — no credit card required
3. Click **Create API Key**
4. Copy the key

### 2. Install and configure

```bash
pip install -r requirements.txt
cp .env.example .env
# open .env and set GEMINI_API_KEY to the key you just copied
```

### 3. Run

```bash
cd app
python -m uvicorn main:app --reload --port 8000
```

Then open:

| Interface | URL |
|---|---|
| Demo UI | http://localhost:8000/app |
| Interactive API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

---

## Project Structure

```
ai_paper_assistant/
├── app/
│   ├── extraction.py        # PDF text extraction + section detection (PyMuPDF + font heuristics)
│   ├── chunking.py          # Splits sections into appropriately sized chunks
│   ├── config.py            # Centralized settings (reads .env) + logging
│   ├── llm_client.py        # Unified Gemini API client (retries, JSON mode, custom exceptions)
│   ├── summarization.py     # Overall + per-section summarization
│   ├── keywords.py          # Classified keyword extraction (topic / method / domain)
│   ├── questions.py         # Review question generation by difficulty
│   ├── title_generator.py   # Title suggestion based on the abstract
│   ├── qa.py                # Lightweight RAG: TF-IDF retrieval + Gemini for answering
│   ├── main.py               # FastAPI app wiring everything together + exception handlers
│   ├── static/index.html     # Demo front-end (no Postman required)
│   └── uploads/               # Uploaded PDFs (git-ignored)
├── tests/
│   └── test_extraction_and_chunking.py   # Unit tests (no API key required)
├── requirements.txt
├── Dockerfile
├── .env.example
└── .gitignore
```

---

## Running with Docker

```bash
docker build -t paper-assistant .
docker run -e GEMINI_API_KEY=your-key -p 8000:8000 paper-assistant
```

---

## Running Tests

```bash
pip install pytest
cd app && pytest ../tests -v
```

Tests cover PDF extraction and chunking only (no Gemini API calls), so they run in any CI pipeline without requiring a real API key.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload` | Upload a PDF. Returns a `paper_id` used by all other endpoints. |
| `GET` | `/summarize/{paper_id}` | Overall summary, or per-section with `?per_section=true`. |
| `GET` | `/keywords/{paper_id}` | Classified keyword extraction. |
| `GET` | `/questions/{paper_id}` | Review questions across difficulty levels. |
| `GET` | `/title/{paper_id}` | Extracted title + an LLM-suggested title. |
| `POST` | `/ask` | Free-form Q&A grounded in the paper's content. |
| `DELETE` | `/paper/{paper_id}` | Remove a paper and its file. |
| `GET` | `/health` | Health check. |

### Example workflow

```bash
# 1. Upload
curl -X POST http://localhost:8000/upload -F "file=@paper.pdf"
# -> { "paper_id": "...", "title_guess": "...", "sections": [...] }

# 2. Summarize
curl http://localhost:8000/summarize/<paper_id>
curl "http://localhost:8000/summarize/<paper_id>?per_section=true"

# 3. Keywords
curl http://localhost:8000/keywords/<paper_id>

# 4. Review questions
curl http://localhost:8000/questions/<paper_id>

# 5. Suggested title
curl http://localhost:8000/title/<paper_id>

# 6. Ask a question
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"paper_id": "<paper_id>", "question": "What methodology was used?"}'

# 7. Clean up
curl -X DELETE http://localhost:8000/paper/<paper_id>
```

---

## Why Gemini instead of Claude/OpenAI?

Google AI Studio offers a genuine free tier — not a trial credit that expires — with no billing information required, and a daily request limit that's more than enough for coursework development and testing. This is the key difference from Claude/OpenAI, which require paid credit shortly after a short trial period.

---

## Key Design Decisions

**1. Section detection via font metadata, not regex alone**
Font size and the bold flag from PyMuPDF are used to identify headings, rather than searching for literal words like "Introduction." This correctly distinguishes an actual section heading from the same word appearing inside a body paragraph.

**2. TF-IDF instead of an embedding model for retrieval**
A deliberate simplification: retrieval happens within a single paper (a small search space), so a heavyweight dependency like `sentence-transformers` isn't necessary. Trade-off worth discussing academically: TF-IDF is faster and lighter, but weaker at matching synonyms and paraphrases compared to embeddings.

**3. Constrained retrieval-augmented generation for `/ask`**
Rather than sending the entire paper as context for every question, only the top 3 most relevant chunks are retrieved and passed to the model as context. This reduces hallucination — the model can say "I don't have enough information" instead of fabricating an answer.

**4. Native JSON mode instead of prompt-only instructions**
Keyword and question extraction use Gemini's `response_mime_type="application/json"` configuration rather than relying solely on prompt instructions asking for JSON, which significantly reduces parsing failures.

**5. Custom retry and exception handling**
Network/rate-limit errors (429) are retried automatically with backoff. Configuration errors (invalid key) or other 4xx errors return immediately with a clear message instead of a raw traceback.

**6. In-memory storage**
Sufficient for coursework and demos. A production deployment would need persistent storage (a database) and would rebuild or persist the TF-IDF index across restarts.

---

## Challenges Encountered

- **Truncated JSON from "thinking" tokens** — `gemini-2.5-flash` performs internal reasoning by default, consuming part of the output token budget before the final answer. This occasionally truncated short structured outputs like keyword lists. Fixed by disabling thinking (`thinking_budget=0`) for deterministic extraction tasks and increasing the token margin.
- **Dependency wheels on newer Python releases** — exact-pinned versions of PyMuPDF and scikit-learn had no prebuilt wheel for very recent Python releases, forcing a from-source build that required a C/C++ compiler. Switched `requirements.txt` to minimum-version bounds (`>=`) so pip always selects a wheel-available version.
- **`.env` discovery depending on working directory** — the app originally only looked for `.env` relative to the current working directory. `config.py` now checks both the project root and `app/`, regardless of where the server is launched from.

---

## Limitations & Future Work

- Uploaded papers are stored in memory only and do not persist across server restarts.
- TF-IDF retrieval doesn't capture semantic similarity as well as embeddings would.
- Scanned (image-only) PDFs without a text layer are not supported.
- A classical extractive summarization baseline (e.g., TextRank) could be added for academic comparison against the LLM-based summary.
- The Gemini free tier has a daily request limit; heavy concurrent use would need a paid tier or request throttling.

---

## Tech Stack

- **FastAPI** — web framework and automatic OpenAPI documentation
- **PyMuPDF (fitz)** — PDF text and font-metadata extraction
- **scikit-learn** — TF-IDF vectorization and cosine similarity for retrieval
- **Google Gemini API** (`google-genai` SDK) — summarization, keyword/question generation, and Q&A
- **pytest** — unit testing for extraction and chunking
- **Docker** — optional containerized deployment

---

## License

This project was built for educational purposes as part of an NLP coursework assignment.
