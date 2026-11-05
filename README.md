# Candidate Communication Platform

Recruiters manage candidates, send single or bulk messages, and track delivery, failures and history.

| Part | Folder | Port | Stack |
|---|---|---|---|
| Web app | `frontend/` | 5173 | React 19, TypeScript, Vite, Material UI, TanStack Query |
| Recruiter API | `backend/` | 8000 | Django, Django REST Framework |
| Dummy provider | `provider/` | 8001 | Separate Django project that behaves like a WhatsApp/email provider |

**Live demo:** https://frontend-liart-eight-10.vercel.app/ (backend on Render's free tier: if the first load fails, wait ~1 minute and refresh)

**Deployment:** frontend on Vercel; API + worker and dummy provider on Render (`render.yaml`). SQLite on Render's free disk resets on restart, and `seed_demo` re-creates the demo data. The dev keys (`dev-provider-key`, `dev-webhook-secret`) are for the demo only; a real deployment would use random secrets.

## Run it

The frontend requires Node.js 20.19.0 or newer (or a current Node.js LTS release).

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt

# 1. provider
cd provider && python manage.py migrate && python manage.py runserver 8001
# 2. API (+ demo data that matches the Figma)
cd backend && python manage.py migrate && python manage.py seed_demo && python manage.py runserver 8000
# 3. worker: sends queued/scheduled messages and retries temporary failures
cd backend && python manage.py run_worker
# 4. web app (proxies /api to :8000)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Without the worker, messages stay "Queued". Set `MESSAGING_EAGER_DISPATCH=true` to send inside the request instead.

Tests: `cd backend && python manage.py test` (80), `cd provider && python manage.py test` (17), `cd frontend && npm test` (14).

## Try the failure cases

Add a candidate whose number ends in one of these (or an email with a `+tag`, e.g. `rahul+invalid@x.com`):

| Suffix | Behaviour |
|---|---|
| `0001` | Invalid recipient, permanent failure (no retry button) |
| `0002` | Rate limited (retried automatically, then manual Retry) |
| `0003` | Fails twice with 503, then succeeds (watch "Retrying" turn into "Sent") |
| `0004` | Accepted, then delivery fails (Failed, retryable) |
| `0005` | Sent and delivered, never read |

Demo switches: `POST :8001/v1/admin/state` with header `Authorization: Bearer dev-provider-key` and body
`{"mode": "normal|rate_limit|outage", "duplicate_webhooks": true, "out_of_order": true}`.
In outage mode the app shows a banner and queued messages go out once the provider is back.

## What the UI covers 

Candidate table (selection, per-column filters, search, pagination, live statuses), Add candidate, Delete (single and multiple copy), Send message drawer (1 or many recipients, chips clamp to 2 lines with "+ n"), Communication history drawer (newest first), empty states (no candidates, no history, no search results), loading skeletons, error states, and toasts.

Beyond the Figma: bulk result dialog with per-candidate outcome and Retry, a "Retrying" state, messaging service health chip, channel picker (WhatsApp/email), message templates with `{{first_name}}`-style placeholders, and scheduled sends.

## API (all errors: `{"error": {"code", "message", "fields?"}}`)

- `GET/POST /api/candidates/`, `GET/PATCH/DELETE /api/candidates/{id}/`, `POST /api/candidates/bulk-delete/`
  - filters: `search`, `name`, `phone`, `code`, `status=read,failed,none`, `last_message_from/to`, `ordering`, `page`, `page_size`
- `GET /api/candidates/{id}/messages/` history, newest first
- `POST /api/messages/bulk/` `{candidate_ids[], body, provider?, scheduled_for?}` (a single send is a batch of one)
- `GET /api/batches/{id}/`, `GET /api/messages/`, `GET /api/messages/{id}/`, `POST /api/messages/{id}/retry/`
- `GET/POST/PATCH/DELETE /api/templates/`, `GET /api/provider-health/`
- `POST /api/webhooks/provider/` (HMAC-signed)

## Design decisions

- **Independent bulk results.** One `Message` per candidate, sent by a worker in isolation, so one failure never blocks the rest.
- **Idempotent, ordered status updates.** Callbacks are logged with a unique `event_id`, so repeats do nothing. Status only moves forward (sent, delivered, read), so a late "delivered" can't overwrite "read".
- **Failure classification.** Permanent (invalid recipient, bad credentials) vs retryable (rate limit, 5xx, timeout). Retryable ones auto-retry with backoff, then offer a manual Retry. Recruiters only see friendly messages.
- **No double sends.** Idempotency key per message plus an atomic claim before sending; stuck "sending" messages are recovered.
- **Provider seam.** `providers.get_provider()` is the only place that knows about providers.
- **Vite instead of Next.js.** This is a single-screen, client-rendered app behind an API, so SSR and routing add nothing. Same React, TypeScript and MUI stack.
- **Polling, not websockets.** The table, history and batch results poll every few seconds, only while something is in flight.
- **Worker without Celery.** A DB-polling command keeps setup simple. For production I'd use Celery/RQ and Postgres.

## Assumptions

- No recruiter login (not in the brief).
- Phone numbers are stored as E.164. A bare 10-digit number typed in the form is treated as +91.
- Deleting a candidate also deletes their message history (as the delete dialog says).
- Figma details adjusted: "Moblie" typo fixed, status labels capitalised ("Read"), and the placeholder button labels named Add candidate / Send message / Delete.
- Scheduled messages can't be cancelled yet.
