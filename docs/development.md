# Development Guide

## Frontend Setup
1. `cd frontend`
2. `npm install`
3. `npm run dev`

## Backend Setup
1. `cd backend`
2. `python -m venv venv`
3. Activate venv (`venv\Scripts\activate`)
4. `pip install -r requirements.txt`
5. `uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload`

The backend **must** be started from `backend/`. `DATABASE_URL`
(`sqlite:///./data/market_radar.db`) and the `.env` file are both resolved
relative to the working directory, so starting from the repository root
silently creates an empty database at `C:\MarketRadar\data\` and fails to load
`SERPAPI_API_KEY` — the app still boots, it is just wired to nothing.

`.claude/launch.json` encodes the correct command and directory, so
`preview_start` with the `backend` configuration always starts it properly.

## Environment Variables
Ensure `backend/.env` contains `SERPAPI_API_KEY` and `FRONTEND_URL`.
Ensure `frontend/.env` contains `VITE_API_BASE_URL`.

---

## Testing a backend change

A stale Uvicorn process has repeatedly looked like a code bug. It happened with
Competitors, with a classifier fix, and with Products: each time the server had
been started before the code existed, without `--reload`, so it kept serving
whatever was on disk at launch. The frontend then showed a 404 or an old
response, and the obvious conclusion — that the new module was broken — was
wrong every time.

Follow this before diagnosing anything:

1. **Check what the running process actually serves.**

   ```
   curl -s http://127.0.0.1:8001/openapi.json | python -c "import sys,json;[print(p) for p in sorted(json.load(sys.stdin)['paths'])]"
   ```

   If the route you expect is not listed, you are not testing the current code.

2. **Restart the backend if the route is absent.** Use the `backend` launch
   configuration, or the command above.

3. **Always run with `--reload` during development.** Uvicorn then watches
   `backend/` and restarts itself on every save.

4. **Test the actual HTTP endpoint after implementing.** A passing test suite
   proves the code is right; it does not prove the running server has it.

5. **Never diagnose frontend or API behaviour against an old server process.**

### Telling a stale process from a real fault

A stale process and a genuine bug look identical from the browser. They differ
in `/openapi.json`:

| Symptom | Meaning |
| --- | --- |
| Route missing from `/openapi.json` | Stale process — restart |
| Route listed, but returns the old response body | Stale process — restart |
| Route listed and fails *inside* the handler | A real fault — debug it |

The clearest tell is a placeholder body such as
`{"message": "Endpoint prepared for implementation"}`: that text only exists in
a scaffold that has since been replaced.

### Killing a stale server

Uvicorn's `--reload` runs a **reloader parent and a server child**, and the
listening socket may be attributed to either. Killing the PID that `netstat`
reports can leave the child holding the port, which looks like the kill failed.

```
netstat -ano | findstr ":8001" | findstr LISTENING
powershell "Get-Process python | Select-Object Id,StartTime"
taskkill /PID <pid> /F
```

Kill the **python** process, then confirm the port is genuinely free before
starting a new one.

---

## Database safety

- Tests run against an isolated database. `tests/conftest.py` sets
  `DATABASE_URL` to `tests/_test_market_radar.db` before any `app.*` module is
  imported, and a session-scoped guard refuses to run if that did not take
  effect. Never point the suite at the development database.
- Schema changes are additive. `app/database/schema_sync.py` adds missing
  columns on startup; it never drops, renames or retypes anything, and never
  writes rows. Anything beyond adding a nullable column needs a real migration.
- Model tables are only created if the model is imported. `app/models/__init__.py`
  is the single registration point — add new models there, or the table will
  silently not exist and fail at query time.
