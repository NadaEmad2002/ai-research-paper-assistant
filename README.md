# AI Research Paper Assistant

مساعد ذكي لتحليل أوراق الأبحاث العلمية: استخراج نص، تلخيص، كلمات مفتاحية،
أسئلة مقترحة، توليد عنوان، وإجابة على أسئلة حرة عن الورقة (Q&A عبر RAG خفيف).

يستخدم المشروع **Google Gemini API** (مجاني بدون بطاقة ائتمان عبر Google AI
Studio) بدل Claude/OpenAI، عشان يكون قابل للتشغيل بالكامل من غير أي تكلفة.

## احصلي على مفتاح مجاني (دقيقتين)

1. روحي على **https://aistudio.google.com/app/apikey**
2. سجّلي دخول بحساب Google عادي (بدون بطاقة ائتمان)
3. اضغطي **Create API Key**
4. انسخي المفتاح وحطيه في `.env`

## البنية

```
ai_paper_assistant/
├── app/
│   ├── extraction.py       # استخراج النص وتقسيمه لأقسام (PyMuPDF + heuristics على الخط)
│   ├── chunking.py         # تقسيم الأقسام لـ chunks بحجم مناسب
│   ├── config.py           # إعدادات مركزية (بتقرأ من .env) + logging
│   ├── llm_client.py       # طبقة موحدة للتعامل مع Gemini API (مع retry + exceptions مخصصة)
│   ├── summarization.py    # تلخيص عام + تلخيص لكل قسم
│   ├── keywords.py         # استخراج كلمات مفتاحية مصنّفة (topic/method/domain)
│   ├── questions.py        # توليد أسئلة مراجعة بمستويات صعوبة مختلفة
│   ├── title_generator.py  # اقتراح عنوان بناءً على الـ Abstract
│   ├── qa.py                # RAG خفيف: TF-IDF retrieval + Gemini للإجابة
│   ├── main.py               # FastAPI app بيربط كل حاجة + exception handlers
│   ├── static/index.html     # واجهة تجريبية بسيطة (بدون حاجة لـ Postman)
│   └── uploads/               # ملفات الـ PDF المرفوعة (مش متتبعة في git)
├── tests/
│   └── test_extraction_and_chunking.py   # اختبارات وحدة (مش محتاجة API key)
├── requirements.txt
├── Dockerfile
├── .env.example
└── .gitignore
```

## طريقة التشغيل (محليًا)

```bash
pip install -r requirements.txt
cp .env.example .env
# افتحي .env وحطي GEMINI_API_KEY بتاعك

cd app
uvicorn main:app --reload --port 8000
```

بعدين:
- **الواجهة التجريبية**: http://localhost:8000/app
- **توثيق تفاعلي (Swagger)**: http://localhost:8000/docs
- **health check**: http://localhost:8000/health

## طريقة التشغيل (Docker)

```bash
docker build -t paper-assistant .
docker run -e GEMINI_API_KEY=your-key -p 8000:8000 paper-assistant
```

## الاختبارات

```bash
pip install pytest
cd app && pytest ../tests -v
```

الاختبارات بتغطي الاستخراج والتقسيم فقط (بدون Gemini API) عشان تشتغل في أي CI
من غير ما تحتاجي تحطي مفتاح فعلي.

## استخدام سريع (curl)

```bash
# 1. رفع الورقة
curl -X POST http://localhost:8000/upload -F "file=@paper.pdf"
# هيرجعلك paper_id، استخدميه في الطلبات الجاية

# 2. تلخيص (ملخص عام أو لكل قسم)
curl http://localhost:8000/summarize/<paper_id>
curl "http://localhost:8000/summarize/<paper_id>?per_section=true"

# 3. كلمات مفتاحية
curl http://localhost:8000/keywords/<paper_id>

# 4. أسئلة مقترحة
curl http://localhost:8000/questions/<paper_id>

# 5. عنوان مقترح
curl http://localhost:8000/title/<paper_id>

# 6. سؤال حر
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"paper_id": "<paper_id>", "question": "ما هي المنهجية المستخدمة؟"}'

# 7. حذف ورقة (تنظيف)
curl -X DELETE http://localhost:8000/paper/<paper_id>
```

## ليه Gemini بدل Claude/OpenAI؟

Google AI Studio بيوفر free tier حقيقي (مش رصيد تجريبي بينتهي) بدون ما
تحطي بيانات بطاقة ائتمان، بحد يومي كويس جدًا لمشروع كورس (موديل
`gemini-2.5-flash` الافتراضي هنا). ده الفرق الجوهري عن Claude/OpenAI اللي
بتطلب رصيد مدفوع بعد فترة تجريبية قصيرة.

## قرارات معمارية (مفيدة للتقرير الأكاديمي)

1. **استخراج الأقسام بالـ font metadata مش بالـ regex بس**: بنستخدم حجم
   الخط والـ bold flag من PyMuPDF عشان نحدد العناوين، ده أدق من مجرد
   البحث عن كلمة "Introduction" في النص لأنه بيفرق بين العنوان الفعلي
   والكلمة لو اتذكرت جوه فقرة عادية.

2. **TF-IDF بدل embedding model في الـ Q&A**: قرار متعمد لتبسيط الـ
   dependencies (مفيش حاجة تقيلة زي sentence-transformers). مناسب لأن
   الاسترجاع بيحصل جوه ورقة واحدة بس (مساحة بحث صغيرة)، مش عبر ملايين
   المستندات. Trade-off تقدري تناقشيه في التقرير: TF-IDF أسرع وأخف بس
   أضعف في فهم الترادف (synonyms) مقارنة بالـ embeddings.

3. **RAG بسيط في /ask**: بدل ما نبعت الورقة كلها لكل سؤال، بنسترجع بس
   أقرب 3 chunks للسؤال ونبعتهم كـ context، وده بيقلل الـ hallucination
   لأن الموديل بيتقيد بالمصدر ويقدر يقول "معنديش معلومات كافية" بدل ما يخترع.

4. **response_mime_type="application/json" بدل تعليمات نصية بس**: في
   استخراج الكلمات المفتاحية والأسئلة، بنستخدم خاصية JSON mode الفعلية
   في Gemini API (مش بس نطلب JSON في الـ prompt)، وده بيقلل احتمال فشل
   الـ parsing بشكل كبير.

5. **retry + exception handling مخصص**: أخطاء الشبكة/rate-limit (429)
   بتتعاد تلقائيًا بـ backoff، أما أخطاء الإعداد (مفتاح غلط) أو الـ 4xx
   التانية فبترجع فورًا برسالة عربية واضحة بدل traceback خام.

6. **تخزين في الميموري (PAPERS_STORE)**: كافي لمشروع كورس وdemo. لو
   حابة تحوليه لإنتاج حقيقي، محتاجة persistent storage (database) +
   إعادة بناء الـ TF-IDF index وقت الإقلاع.

## نقطة تحسين ممكنة لو حابة تزودي عمق الكورس

جربي تعملي نسخة extractive classical للتلخيص (TextRank بمكتبة `networkx`
أو `sumy`) وقارنيها بمخرجات Gemini في التقرير — هيدي بعد أكاديمي حقيقي
للمشروع بدل ما يبقى wrapper كامل حوالين LLM API.

## ملاحظة عن حدود الاستخدام المجاني

فيه حد أقصى يومي لعدد الطلبات على الـ free tier (كافي جدًا لتطوير واختبار
مشروع كورس). لو حصل خطأ 503 برسالة "rate limit"، انتظري دقيقة وجربي تاني،
أو قلّلي عدد الطلبات المتتالية وقت الاختبار.
