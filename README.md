# FAILSAFE AI — Resilient LLM Chatbot

A production-style React + FastAPI + SQLite chatbot built around **LLM resilience**: ordered API-key failover, LiteLLM response caching, persistent multi-turn sessions, request-level token/latency metadata, and an assessment-ready failure simulation hook.

## 1. Live URLs
- Frontend: `<add after deploy>`
- Backend: `<add after deploy>` (`/health`, `/docs`)
- Demo video: `<add after recording>`

## 2. Run locally: with Docker and without
### Recommended: Docker
1. Install Docker Desktop and make sure it is running.
2. Copy `.env.example` to `.env`.
3. Put **at least two real provider keys** in `LLM_API_KEYS`.
4. Run `make up`.
5. Open `http://localhost:3000`. Backend health is `http://localhost:8000/health`.
6. Stop with `make down`; inspect logs with `make logs`.

### Without Docker
Backend:
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Set the variables from .env.example for your shell; use DATABASE_URL=sqlite:///./app.db
uvicorn app.main:app --reload --port 8000
```
Frontend (second terminal):
```bash
cd frontend
npm install
# VITE_API_URL defaults to http://localhost:8000
npm run dev
```
Tests: `make test`. Tests use the deterministic mock mode and do not consume real API quota.

## 3. Design decisions: key fallback, caching, SQLite session storage
- **Ordered key pool:** `LLM_API_KEYS` becomes `key_1`, `key_2`, etc. Keys themselves are never returned to the client or logged. Each provider attempt disables provider retries so failover remains deterministic and observable.
- **Failover:** failed attempts move to the next configured key. If all keys fail, `/chat` returns clean JSON `503 {"detail":"all providers unavailable"}` and the failed exchange is not persisted.
- **Assessment failure hook:** when `ENABLE_FAILURE_SIMULATION=true`, `X-Simulate-Failure` can simulate `429/500/502/503` per key for one request. The UI exposes safe presets inside Developer Controls.
- **LiteLLM cache:** built-in local cache uses the model and full message list (system + history + new message). Cache hits return `LLM_CACHE`, `key_id: null`, zero fallbacks and the identical cached reply. Cache is intentionally process-local; SQLite is the persistent store.
- **SQLite sessions:** the required `messages` table is supplemented by a small `sessions` table for the optional system prompt. Writes are transactional and occur only after successful inference. Docker mounts `/data` as a named volume.
- **Observability:** every assistant response exposes resolution source, model, server latency, per-request input/output tokens, key id and fallback count. Server responses also include an `X-Request-ID` and structured request log line without secrets.
- **Frontend:** FAILSAFE AI intentionally visualizes the infrastructure rather than hiding it: system health, cache/live status, routing metadata and failure controls are visible while preserving every required `data-testid`.

## 4. Verification: failover, cache hits and per-message token usage
```bash
B=http://localhost:8000
curl $B/health
curl -s $B/chat -H 'content-type: application/json' -d '{"session_id":"a1","message":"Capital of France?"}'
curl -s $B/chat -H 'content-type: application/json' -d '{"session_id":"b2","message":"Capital of France?"}'
curl -s $B/chat -H 'content-type: application/json' -H 'X-Simulate-Failure: key_1=429' -d '{"session_id":"c3","message":"Say hi"}'
curl -s -i $B/chat -H 'content-type: application/json' -H 'X-Simulate-Failure: *=429' -d '{"session_id":"c3","message":"This must fail"}'
curl -s $B/sessions/a1/messages
```
Expected: first unique request is `LIVE_INFERENCE`; the identical first request in a new session is `LLM_CACHE` and faster; `key_1=429` succeeds through `key_2` with one fallback; `*=429` returns 503 and is not added to history.

## 5. Setup Used: editor and AI tools
VS Code, Docker Desktop, Git/GitHub, React/Vite, FastAPI, LiteLLM, SQLite, pytest, and AI-assisted development/review. Update this sentence before submission if your actual setup differs.

## 6. Bonus features
- Bold responsive FAILSAFE AI interface with infrastructure status.
- Optional per-session system prompt.
- Developer failure presets plus custom simulation header value.
- Key route and fallback count shown with every reply.
- Friendly loading, validation, provider-failure and connectivity states.
- Deterministic `MOCK_LLM` test mode that avoids real API usage.
- Request IDs and secret-safe server logging for troubleshooting.

## Repository structure
```text
/backend                 FastAPI, LiteLLM gateway, SQLite, tests
/frontend                React/Vite UI served by nginx in Docker
docker-compose.yml       Full local stack
Makefile                 up / down / logs / test
.env.example             Placeholder configuration only
README.md                Setup, architecture and verification
```

## Security checklist
- Never commit `.env` or real API keys.
- Keep `ENABLE_FAILURE_SIMULATION=true` for the required assessment deployment/demo; disable it for a normal production deployment after assessment.
- Set `ALLOWED_ORIGINS` to the exact deployed frontend origin rather than `*`.
- Do not log provider keys.
