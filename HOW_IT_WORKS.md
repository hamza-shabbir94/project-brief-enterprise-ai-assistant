# IronStore Assistant — How it works

A RAG (Retrieval-Augmented Generation) chatbot for IronStore employees, built with LangChain,
OpenAI and Pinecone. It has a React + Vite frontend and a FastAPI backend, deployed on Vercel.

## The idea in one picture

```
 ingest.py (run once, on your laptop)         every question
 ────────────────────────────────────         ──────────────
 83 PDFs                                      React page (frontend/)
   │  PyPDFLoader                                │  POST /api/chat {"question", "history"}
   ▼                                             ▼
 text  ──split──▶  2,486 chunks               FastAPI (api/index.py)
   │  + metadata (title, page, department,       │  calls ask() in rag.py
   │    last_reviewed, outdated)                 ▼
   ▼                                          follow-up? rewrite it as a standalone question
 OpenAI embeddings ──▶ Pinecone index            │  ("and for contractors?" → "...policy for contractors?")
                                                 ▼
                                              Pinecone: find the 6 most similar chunks
                                                 │  (skip outdated documents and weak matches;
                                                 │   none left → "I couldn't find it", no LLM call)
                                                 ▼
                                              prompt = rules + numbered chunks + history + question
                                                 │
                                                 ▼
                                              gpt-4o-mini ──▶ answer with [1][2] citations
                                                 │
                                                 ▼
                                              JSON {answer, sources} ──▶ shown in the page
```

The LLM never "knows" IronStore's policies. We **retrieve** the relevant text first and
**augment** the prompt with it, so the model **generates** an answer from real documents.

## Project structure

```
project-brief-enterprise-ai-assistant/
├── frontend/                 React + Vite app (what the user sees)
│   ├── src/
│   │   ├── App.jsx           chat state: messages, loading, sending questions
│   │   ├── api.js            the one place that calls the backend
│   │   ├── index.css         all styling (light + dark mode, mobile)
│   │   └── components/
│   │       ├── Welcome.jsx   greeting + clickable example questions
│   │       ├── Message.jsx   a chat bubble, markdown, citation chips, sources
│   │       ├── ChatInput.jsx the text box at the bottom
│   │       └── Icons.jsx     small SVG icons
│   └── vite.config.js        forwards /api to the backend during development
├── api/
│   └── index.py              FastAPI backend: POST /api/chat, GET /api/health
├── rag.py                    retrieve chunks + prompt + LLM → answer
├── vector_store.py           connects to Pinecone (or Chroma)
├── ingest.py                 PDFs → chunks → embeddings → Pinecone
├── config.py                 all settings in one place
├── evaluation/               measures answer quality (see "Evaluation" below)
│   ├── dataset.json          26 test questions with reference answers
│   ├── evaluate.py           runs them through the assistant and scores them
│   ├── metrics.py            retrieval, keyword, refusal, ROUGE-L, similarity scores
│   ├── judge.py              LLM-as-a-judge grading (correctness, groundedness)
│   ├── test_metrics.py       offline tests: `python -m pytest evaluation`
│   └── results/              one JSON + Markdown report per run
├── streamlit_app.py          Streamlit prototype (local only, handy for quick tests)
├── requirements.txt          backend packages (what Vercel installs)
├── requirements-dev.txt      + packages for ingestion and Streamlit (local work)
├── vercel.json               tells Vercel how to build the frontend and run the backend
└── .vercelignore             files Vercel doesn't need (PDFs, .venv, ...)
```

### The API

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/api/health` | — | `{"status": "ok"}` |
| `POST` | `/api/chat` | `{"question": "And for contractors?", "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}` | `{"answer": "...", "search_query": "...", "sources": [{"number", "title", "page", "department", "last_reviewed", "score", "excerpt"}]}` |

`history` is optional: the earlier messages of the conversation, so follow-up questions work. The
React app and the Streamlit app send it automatically. `search_query` is the follow-up rewritten as
a standalone question (what was actually searched), and `score` is each chunk's similarity (0–1).

When the backend is running locally, FastAPI also gives you interactive docs at
http://localhost:8000/docs, where you can try the API in the browser.

## Choosing a vector store

The vector store holds the chunks and their embeddings and finds the most similar ones for a
question. Pick one with `VECTOR_STORE` in `config.py`. The rest of the code stays the same,
because LangChain gives every vector store the same interface (`add_documents`, `as_retriever`).

| | **Pinecone** (default) | Chroma | Elasticsearch |
|---|---|---|---|
| Where data lives | Pinecone's cloud | `chroma_db/` folder on your computer | An Elasticsearch cluster (Elastic Cloud or self-hosted) |
| Setup | API key only | Nothing | Cluster URL + API key |
| Works when deployed | ✅ Same index locally and online | ❌ Folder must be shipped with the app | ✅ |
| Free option | Starter plan (plenty for this project) | Always free | 14-day Elastic Cloud trial |
| Extra strengths | Simple, serverless | Offline, good for experiments | Keyword + vector (hybrid) search, good for exact SKUs |
| In this project | ✅ Implemented | ✅ Implemented (local only) | Not yet (see ideas below) |

We use **Pinecone** because the deployed app connects to the same cloud index you fill from
your laptop, so there are no database files to ship.

To try Chroma locally: `pip install langchain-chroma`, set `VECTOR_STORE = "chroma"` in
`config.py`, and run `python ingest.py` again.

## Run it locally

You need **Python 3.10+**, **Node.js 20+**, an **OpenAI API key** and a **Pinecone API key**
(free at https://app.pinecone.io).

### One-time setup

**1. Go to the project folder**

```bash
cd project-brief-enterprise-ai-assistant
```

**2. Create a Python virtual environment and install the backend packages**

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

Your terminal prompt now starts with `(.venv)`. Activate it again in every new terminal.

**3. Install the frontend packages**

```bash
cd frontend
npm install
cd ..
```

**4. Add your API keys**

```bash
cp .env.example .env
```

Open `.env` and fill in `OPENAI_API_KEY` and `PINECONE_API_KEY`. The code also finds a `.env` in any
parent folder, so if you already have one higher up (e.g. `Ironhack_AI_Bootcamp/.env`) you can skip this step.
Never commit `.env`. It is already listed in `.gitignore`.

**5. Build the knowledge base** (again whenever the PDFs change)

```bash
python ingest.py
```

This takes a couple of minutes and costs about $0.01. It creates a Pinecone index called
`ironstore-assistant` and uploads all chunks to it. You can see it in the Pinecone console.
Re-running it deletes and rebuilds that index only. Your other indexes are not touched.

### Every time you work on it: two terminals

The backend and frontend are two separate programs, so run each in its own terminal.

**Terminal 1: backend** (from the project folder, with `.venv` active)

```bash
uvicorn api.index:app --reload --port 8000
```

`--reload` restarts the server automatically when you change a Python file.

**Terminal 2: frontend**

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**. Vite reloads the page instantly when you change a React file.
Requests to `/api/...` are forwarded to the backend on port 8000 (see `vite.config.js`).

Stop either one with `Ctrl + C`.

> Quick alternatives without the React app: `streamlit run streamlit_app.py` (simple browser UI) or
> `python rag.py` (chat in the terminal).

### Common problems

| Problem | Fix |
|---|---|
| Page says *"Something went wrong"* on every question | The backend isn't running. Start Terminal 1 |
| `No Pinecone index found. Run python ingest.py first.` (in Terminal 1) | Run step 5 |
| `OpenAIError: The api_key client option must be set` | Your `.env` is missing or has the wrong variable name. It must be `OPENAI_API_KEY` |
| `PineconeConfigurationError: You haven't specified an API key` | Add `PINECONE_API_KEY` to your `.env` |
| `ModuleNotFoundError: No module named ...` | The virtual environment isn't active. Run `source .venv/bin/activate` |
| `uvicorn: command not found` | Same: activate `.venv`, then `pip install -r requirements-dev.txt` |
| `Port 5173 is in use` | Another `npm run dev` is still running. Close it, or use the URL Vite prints |
| `ForbiddenException: ... max serverless indexes` | The free plan allows 5 indexes. Delete an unused one in the Pinecone console |

## Deploy to Vercel

### How Vercel runs this project

The project uses **Vercel Services**: one Vercel project that contains two separate apps
(a frontend and a backend), served from the same URL:

```
https://your-app.vercel.app/            ──▶  "frontend" service: React app in frontend/ (built by Vite)
https://your-app.vercel.app/api/chat    ──▶  "backend" service:  FastAPI app in api/index.py
```

`vercel.json` defines the two services and routes requests to them:

```json
{
  "services": {
    "backend":  { "root": ".",         "framework": "fastapi", "entrypoint": "api.index:app" },
    "frontend": { "root": "frontend/", "framework": "vite" }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "backend" } },
    { "source": "/(.*)",     "destination": { "service": "frontend" } }
  ]
}
```

| Part | What it means |
|---|---|
| `backend.root: "."` | The backend uses the project folder, because it needs `rag.py`, `config.py`, ... next to `api/` |
| `backend.entrypoint: "api.index:app"` | "The FastAPI object called `app` in `api/index.py`" |
| `frontend.root: "frontend/"` | Vercel builds the React app inside `frontend/` (`npm install` + `npm run build`) |
| `rewrites` | Checked from top to bottom: `/api/...` goes to FastAPI, everything else to React. The backend sees the full path (`/api/chat`), which is why the FastAPI routes start with `/api` |

> **Why the Streamlit file is called `streamlit_app.py`:** Vercel automatically treats a file named
> `app.py` in the root as a FastAPI app. If the Streamlit prototype were named `app.py`, Vercel
> would try to run it as the backend and fail.

**Test the Vercel setup locally before pushing.** `vercel dev` runs both services behind
Vercel's router, exactly as in production (`-L` means no Vercel login is needed):

```bash
source .venv/bin/activate          # so the backend uses your installed packages
npx vercel@latest dev -L           # → http://localhost:3000
```

For the Python function, Vercel installs `requirements.txt`. That file holds only what the backend
needs. Ingestion and Streamlit packages live in `requirements-dev.txt`, which keeps the function
small. The PDFs aren't uploaded at all (`.vercelignore`), because the knowledge base is already
in Pinecone.

### Before you deploy

1. Run `python ingest.py` locally so Pinecone has the data. The deployed app reads from that same index.
2. Make sure the app works locally (see above).
3. Push the project to GitHub. `.env` stays out because it's in `.gitignore`.

   ```bash
   git add .
   git commit -m "IronStore assistant: React frontend + FastAPI backend"
   git push
   ```

### Option 1: Deploy from GitHub (easiest)

1. Go to https://vercel.com/new and sign in with GitHub.
2. **Import** your repository.
3. On the configuration screen:
   - **Root Directory:** keep the **repository root** selected, *not* `frontend`. Only the root
     contains `vercel.json` and both services. Choosing `frontend` would deploy the page without
     the backend.
   - Vercel should show it as a multi-service project with **backend (FastAPI)** and
     **frontend (Vite)**. If it suggests its own `vercel.json`, ignore it: ours is already in the repo.
   - **Environment Variables:** add both keys:
     | Name | Value |
     |---|---|
     | `OPENAI_API_KEY` | `sk-...` |
     | `PINECONE_API_KEY` | `pcsk_...` |
4. Click **Deploy** and wait 1–3 minutes.
5. Open the URL Vercel gives you and ask a question.

From now on, every `git push` to the main branch redeploys automatically, and every other branch
gets its own preview URL.

### Option 2: Deploy from the terminal

```bash
npm install -g vercel              # one-time: install the Vercel CLI
vercel login
vercel                             # first run: answers a few questions and links the project
vercel env add OPENAI_API_KEY      # paste the key; select Production and Preview
vercel env add PINECONE_API_KEY
vercel --prod                      # deploy to production
```

### Check that it works

```bash
curl https://your-app.vercel.app/api/health
# {"status":"ok"}
```

If questions fail, open your project in the Vercel dashboard → **Logs**. Errors from
`api/index.py` show up there, e.g. a missing API key.

| Problem on Vercel | Fix |
|---|---|
| Page loads, but every answer says *"Something went wrong"* | Check **Logs**. Usually a missing environment variable. After adding one, **redeploy** (variables only apply to new deployments) |
| `No Pinecone index found` in the logs | Run `python ingest.py` locally (same Pinecone account as the key on Vercel) |
| `404` on `/api/chat` | `vercel.json` or `api/index.py` wasn't committed. Check `git status` |
| First question after a while is slow | A "cold start": the function is loading Python libraries. Later questions are faster |

### Important: costs and access

- **The URL is public.** Anyone who has it can ask questions, and each question uses your OpenAI
  credits. Set a monthly **usage limit** in your OpenAI account settings.
- These documents are meant to be *internal*. For a class demo a public URL is fine, but a real
  company deployment would need a login (see the ideas below).
- When you change the PDFs, just run `python ingest.py` again. The live app uses the updated
  index immediately, with no redeploy needed.

## How the messy data is handled

While inspecting the documents I found:

| Problem in the data | How the assistant handles it |
|---|---|
| `IronStore_Old_Product_Catalog_2021.pdf` is outdated (reviewed Dec 2021, all others Aug 2026) | `ingest.py` reads each document's "Last reviewed" date and marks old ones `outdated=True`. The retriever filters them out, so the assistant never quotes 2021 prices |
| Some products appear twice in a catalog (e.g. once active, once "discontinued") | The prompt tells the LLM to flag discontinued products and name the replacement SKU |
| Products and sections continue across page breaks | Pages are joined before splitting, so chunks don't stop at page edges. Page numbers are still tracked for citations |
| The PDFs use an invisible control character as bullet points | Replaced with `•` during ingestion |
| Questions the documents can't answer | Chunks with a similarity below `MIN_RELEVANCE` (0.30) are dropped. If none are left (e.g. "What is the capital of France?"), the assistant answers "I couldn't find it" without calling the LLM. Otherwise the prompt requires answers only from the sources, with "I couldn't find it" and a suggestion of who to ask, instead of guessing. The UI then shows "No sources used" |
| The same file added twice | Identical chunks are de-duplicated before embedding |

## Example questions

- What is our remote work policy?
- How do I request time off?
- What is the return policy for customers?
- How much does the Nordview NQ-55U7 TV cost and is it in stock?
- Is the Heritage Candle Lantern still available?  → *discontinued*
- How much is the IronStore 24" Full HD Office Monitor?  → *only in the 2021 catalog, so "not found"*
- What is the mileage reimbursement rate? → then: *And how much can I claim for dinner?*  → *follow-up*

## Evaluation

`evaluation/` checks the assistant automatically on 26 test questions, so you can tell whether a
change (prompt, chunk size, `TOP_K`, model, ...) actually made it better.

```bash
python -m evaluation.evaluate              # all questions + LLM judge (~$0.05, about a minute)
python -m evaluation.evaluate --no-judge   # without the judge: cheaper, rule-based scores only
python -m evaluation.evaluate --category follow_up
python -m evaluation.evaluate --ids fin-mileage,oos-capital
python -m pytest evaluation                # offline tests of the scoring code (free)
```

**The test set** (`dataset.json`) was written by reading the PDFs. Each case has a question, a
reference answer, the document(s) it should come from, and key facts that must (or must not)
appear in the answer. It covers the tricky parts of the data on purpose:

| Category | Cases | What it checks |
|---|---:|---|
| `policy` | 15 | HR, Finance, IT, Deliveries, Customer support and Sales procedures |
| `product` | 2 | Prices, stock and warehouse locations from the catalogs |
| `discontinued` | 2 | Discontinued products are flagged as such |
| `outdated` | 1 | A product only in the 2021 catalog is "not found", and its old price never appears |
| `out_of_scope` | 3 | Questions the documents can't answer get "I couldn't find it", not a guess |
| `follow_up` | 3 | Questions that only make sense with the earlier conversation |

**The metrics**, from cheap to expensive (the types of evals from the course):

| Metric | Type | Meaning |
|---|---|---|
| Retrieval hit rate | Code-based | Was a chunk from the right document retrieved? |
| Retrieval MRR | Code-based | How high was it ranked? 1 = first, 0.5 = second, ... |
| Keyword recall | Code-based | Share of the key facts (e.g. "€45", "14 characters") found in the answer |
| Refusal accuracy | Code-based | Said "I couldn't find it" exactly when it should have |
| Citation rate | Code-based | Answers that cite their sources like [1] |
| ROUGE-L | Reference-based, lexical | Word overlap with the reference answer |
| Semantic similarity | Reference-based, embeddings | Cosine similarity between answer and reference embeddings |
| Judge correctness (1–5) | LLM-as-a-judge | `gpt-4o` compares the answer with the reference |
| Judge grounded | LLM-as-a-judge | `gpt-4o` checks every fact is in the retrieved sources (no hallucination) |

A case **passes** when the key facts are there, nothing forbidden appears, the refusal behaviour is
right, and the judge gives correctness ≥ 4 and grounded = yes. ROUGE-L and similarity are only
reported, because a correct answer worded differently from the reference scores low on them.

**Results** are saved in `evaluation/results/` as JSON (every answer and score) and a Markdown
report (summary, per-category table, and the answers of the failed cases with the judge's reasoning).
Each run is compared with the previous run on the same questions:

Current results (November 2026, `gpt-4o-mini` answering, `gpt-4o` judging):

| Metric | Score |
|---|---:|
| Pass rate | 1.00 (26/26) |
| Retrieval hit rate / MRR | 1.00 / 0.94 |
| Keyword recall | 1.00 |
| Refusal accuracy | 1.00 |
| Citation rate | 0.95 |
| ROUGE-L | 0.54 |
| Semantic similarity | 0.81 |
| Judge correctness (1–5) | 4.96 |
| Judge grounded | 1.00 |
| Avg. latency | 1.6 s |

A perfect pass rate on 26 questions means the test set is now too easy to catch regressions on
its own. Add harder cases (multi-document questions, ambiguous wording, duplicated products) as
you find them.

The report also shows the best similarity score of answerable vs. unanswerable questions, which
helps choose `MIN_RELEVANCE` in `config.py`. To add a test, add an entry to `dataset.json`
(`python -m pytest evaluation` checks that it is well-formed). `--fail-under 0.9` makes the command
fail when the pass rate drops, so it can run in CI.

## Ideas for adding complexity later

1. ~~**Conversation memory.**~~ ✅ Done: the last `HISTORY_MESSAGES` messages are sent with each
   request and follow-ups are rewritten into standalone questions before retrieval.
2. **Streaming answers.** Show the answer word by word as it's generated (FastAPI
   `StreamingResponse` + LangChain `.stream()`), like ChatGPT.
3. **Login.** Only let IronStore employees in, e.g. with Clerk, Auth0 or Vercel's deployment protection.
4. **Metadata filters.** Let the user pick a department (HR, Finance, ...) and pass it to the
   retriever's `filter`.
5. **Better retrieval.** Multi-query retriever (like lab04), or hybrid search (keywords +
   vectors) so exact SKUs like `TV-NDV-NQ55U7` are always found. Elasticsearch supports
   hybrid search out of the box. Add it as a third option in `vector_store.py` with
   `langchain-elasticsearch` (`ElasticsearchStore`).
6. **Smarter chunking for catalogs.** Split on each product (`SKU:`) so one chunk = one product.
7. ~~**Evaluation.**~~ ✅ Done: see [Evaluation](#evaluation). Next step: grow the test set,
   e.g. with questions real employees ask.
8. **Agent with tools.** E.g. a "check stock" tool or "create IT ticket" tool alongside RAG.
