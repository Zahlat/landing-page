Meraki — Contact Messages Backend Plan
Nov 7, 2026 · @Salman
Summary
Visitors send a message (name, email, type, content) through a form on /[lang]/contact. Next.js receives it and forwards it to a private FastAPI service, which validates it, applies free spam and rate-limit checks, and stores it in PostgreSQL. A basic admin area at /admin lets the team log in and read, mark, archive and delete messages.
`Decision
Choice
Storage
PostgreSQL (local now), SQLAlchemy 2 async + Alembic
Notification
None for now: messages live in the DB and are read in the admin page
Spam protection
Free only: honeypot, minimum fill time, link limit, duplicate check, rate limit per IP and per email
Browser → backend
Browser talks only to Next.js; Next.js calls FastAPI server-side with a shared token. FastAPI is never public
Admin
Basic: login, list with filters, detail, status change, delete
Message type
Fixed set (suggestion, request, question, other) as a Python StrEnum + DB CHECK constraint
Admin auth
DB-backed users (Argon2 hashes) + opaque server-side sessions in an httpOnly cookie
Architecture
The dashed zone is the trust boundary: the internet reaches only Next.js. FastAPI accepts a request only if it carries the internal token, and in production it listens on a private address (127.0.0.1 or the host's private network), so it is never exposed even if the token leaked.
Database schema
Three tables: contact_messages, admin_users, admin_sessions. Every limit is enforced twice, once in Pydantic and once as a DB constraint, so bad data cannot get in through a bug or a manual insert.
Message type design. Use a Python StrEnum (suggestion, request, question, other) mapped with sa.Enum(MessageType, native_enum=False, create_constraint=True, length=20). That stores a VARCHAR(20) with a CHECK constraint, not a native Postgres ENUM. A native ENUM is awkward to change later (removing or renaming values needs a type rebuild). The CHECK version changes with an ordinary Alembic migration. The DB and API hold only the code (request). The Arabic and English labels live in content/ar.ts and content/en.ts. Message status (new, read, archived) uses the same pattern.
contact_messages
Column
Type
Rules
id
BIGINT GENERATED ALWAYS AS IDENTITY
PK. Never returned to the public endpoint
name
VARCHAR(100)
NOT NULL, trimmed, 1–100 chars
email
VARCHAR(254)
NOT NULL, validated with EmailStr, stored lowercased
type
VARCHAR(20) + CHECK
NOT NULL, one of the enum values
content
TEXT + CHECK char_length <= 5000
NOT NULL, 10–5000 chars
locale
VARCHAR(2) + CHECK in (ar,en)
NOT NULL; which site language it came from
status
VARCHAR(20) + CHECK
NOT NULL, default new
ip_hash
CHAR(64)
HMAC-SHA256 of the client IP with a server secret. Raw IP is never stored
content_hash
CHAR(64)
SHA-256 of normalized email + content, for duplicate detection
user_agent
VARCHAR(512)
Nullable, truncated
created_at
TIMESTAMPTZ
NOT NULL, default now()
read_at
TIMESTAMPTZ
Nullable, set when status first leaves new
Indexes, each one matching a real query:
• (status, created_at DESC, id DESC): admin list filtered by status, keyset pagination
• (created_at DESC, id DESC): admin list with no filter
• (ip_hash, created_at): rate limit count per IP
• (email, created_at): rate limit count per email
• (content_hash, created_at): duplicate check
admin_users
Column
Type
Rules
id
BIGINT IDENTITY
PK
email
VARCHAR(254)
UNIQUE, lowercased
password_hash
VARCHAR(255)
Argon2id
is_active
BOOLEAN
default true
failed_login_count
INTEGER
default 0
locked_until
TIMESTAMPTZ
Nullable
last_login_at
TIMESTAMPTZ
Nullable
created_at
TIMESTAMPTZ
default now()
admin_sessions
Column
Type
Rules
id
BIGINT IDENTITY
PK
token_hash
CHAR(64)
UNIQUE. SHA-256 of the session token; the raw token exists only in the cookie
admin_user_id
BIGINT
FK → admin_users.id, ON DELETE CASCADE, indexed
created_at
TIMESTAMPTZ
default now()
expires_at
TIMESTAMPTZ
NOT NULL, created_at + 8 h
revoked_at
TIMESTAMPTZ
Nullable, set on logout
API contract (FastAPI)
All routes are under /v1 and every request must carry X-Internal-Token: <shared secret>. A missing or wrong token gets 401, checked with hmac.compare_digest. Only Next.js knows the token. Interactive docs (/docs, /openapi.json) are on in dev and off in production.
Method + path
Auth
Request
Responses
GET /health
none
—
200 {"status":"ok"} (also checks the DB connection)
POST /v1/messages
internal token
body {name, email, type, content, locale}, headers X-Client-IP, X-Client-UA
202 {"status":"received"} · 422 validation · 429 + Retry-After
POST /v1/admin/auth/login
internal token
{email, password} + X-Client-IP
200 {token, expires_at} · 401 generic "invalid credentials" · 429 when locked
POST /v1/admin/auth/logout
admin bearer
—
204 (session revoked)
GET /v1/admin/me
admin bearer
—
200 {email}
GET /v1/admin/messages
admin bearer
query status?, type?, cursor?, limit (1–50, default 20)
200 {items:[…], next_cursor}
GET /v1/admin/messages/stats
admin bearer
—
200 {new, read, archived} counts
GET /v1/admin/messages/{id}
admin bearer
—
200 full message · 404
PATCH /v1/admin/messages/{id}
admin bearer
{status}
200 updated message · 404 · 422
DELETE /v1/admin/messages/{id}
admin bearer
—
204 · 404
Admin routes carry Authorization: Bearer <session token> as well as the internal token. Next.js reads the token from the admin's cookie and adds the header server-side.
Rules for every endpoint:
• Request schemas use model_config = ConfigDict(extra="forbid", str_strip_whitespace=True), so unknown fields are rejected and whitespace is trimmed.
• Response schemas are explicit, so internal fields (ip_hash, content_hash, password_hash) are never serialized.
• One error shape everywhere: {"error": {"code": "rate_limited", "message": "..."}}. 500s never return stack traces.
• Pagination uses a keyset, not OFFSET. next_cursor is base64 of (created_at, id) of the last row, and the query is WHERE (created_at, id) < (:c, :i) ORDER BY created_at DESC, id DESC LIMIT :n+1. Speed stays constant however many messages pile up.
• The list endpoint returns a preview (first 160 chars of content), not the full text. The full text comes only from the detail endpoint.
• Request body size is capped at 16 KB before parsing.
Spam protection and rate limiting (all free)
The layers below cost nothing and need no outside service. Cheap checks run first in Next.js. The checks that decide run in FastAPI, where they are unit-tested.
#
Check
Where
Rule
On failure
1
Honeypot
Next.js
Hidden website field (off-screen, tabIndex=-1, autoComplete="off"). Humans leave it empty
Fake success, nothing sent to backend
2
Minimum fill time
Next.js
The form carries a signed timestamp (HMAC with FORM_SIGNING_SECRET) set when the page renders. Reject if under 3 s or over 24 h old, or if the signature is wrong
Fake success
3
Validation
Both
Same limits in a Zod schema (Next) and Pydantic (FastAPI). FastAPI is the authority
422, field errors shown in the user's language
4
Link limit
FastAPI
More than 3 URLs in content
422 "too many links"
5
Rate limit per IP
FastAPI
Max 5 messages per ip_hash per hour
429 + Retry-After
6
Rate limit per email
FastAPI
Max 3 messages per email per hour
429
7
Duplicate
FastAPI
Same content_hash within 24 h
Fake 202, not stored
8
Login protection
FastAPI
5 failed logins → account locked 15 min; max 10 login attempts per IP per 15 min
429
Why rate limits use Postgres, not an in-memory library. An in-memory counter like slowapi's default resets on restart and isn't shared between uvicorn workers. Counting recent rows with the indexes above (SELECT count(*) … WHERE ip_hash = :h AND created_at > now() - interval '1 hour') is exact, survives restarts and costs one indexed query. Add Redis only when traffic actually needs it.
Client IP, the one thing that's easy to get wrong. FastAPI sees Next.js as the client, so Next must send the real visitor IP in X-Client-IP. Next should take it only from the header your hosting platform guarantees, never from the raw left-most X-Forwarded-For value, which the visitor can forge. FastAPI trusts X-Client-IP only because the internal token proves Next sent it. Locally the IP will be 127.0.0.1 or missing: use a fallback of "unknown" and keep the limit working.
Free upgrade if bots get through: Cloudflare Turnstile has a free tier and needs one server-side verification call. It's left out of v1 to keep things simple.
Admin auth and admin page
Admins log in with email + password. There is no sign-up endpoint: admins are created from the command line with uv run python -m app.cli create-admin.
Login flow
1. The /admin/login form posts to a Next.js Server Action.
2. The Server Action calls POST /v1/admin/auth/login. FastAPI checks the Argon2 hash. On success it creates a random 32-byte token (secrets.token_urlsafe(32)), stores only its SHA-256 in admin_sessions, and returns the raw token.
3. Next.js sets the cookie __Host-meraki_admin: HttpOnly, Secure, SameSite=Strict, Path=/, Max-Age 8 h. The __Host- prefix makes the browser refuse the cookie unless it's Secure, has no Domain and has Path /. On local http:// use the plain name meraki_admin without Secure.
4. Each admin page and action reads the cookie and sends it to FastAPI as a Bearer token. FastAPI hashes it, finds a session that isn't expired or revoked, and loads an active user.
5. Logout revokes the session in the DB and deletes the cookie.
Sessions are opaque and server-side rather than JWTs because logout and "kick this session" work instantly with a single row update. The cost, one indexed lookup per admin request, doesn't matter at this scale.
Security rules for the admin area
• Check auth in every Server Action and in the data fetch, not only in the layout. Server Actions are public POST endpoints: a layout check doesn't protect them.
• Login failures always return the same message and take about the same time (verify against a dummy hash when the email doesn't exist), so attackers can't tell which emails are real.
• Message content is shown as plain text through React's normal escaping. Never use dangerouslySetInnerHTML and never render it as markdown: it's attacker-controlled input.
• Add robots: { index: false } metadata and an X-Robots-Tag: noindex header on /admin.
• CSRF: SameSite=Strict plus the built-in origin check on Next.js Server Actions covers it.
Pages (English only, plain styling)
Route
Shows
Actions
/admin/login
Email + password form
Log in
/admin/messages
Table: date, name, email, type, preview, status badge. Filter tabs New / Read / Archived / All plus a type dropdown. "Load more" button using the cursor
Open a message
/admin/messages/[id]
Full message, metadata (locale, date, user agent)
Mark read / unread, archive, delete (with confirm)
Header on every admin page
Count of new messages, logged-in email
Log out
Opening a message does not mark it as read on the server automatically (a GET must not change data). The detail page calls the PATCH Server Action once when it loads, or you can make marking read a button: pick one.
Backend folder layout
A layered layout: routes → services → repositories → models. Routes handle only HTTP. Services hold the business rules (spam, rate limit, auth). Repositories hold only SQL. This is the Spring-style controller/service/repository split you already know, written in Python.
meraki-starter/
├── src/                          # Next.js app (existing)
├── backend/
│   ├── pyproject.toml            # uv; deps + ruff + mypy + pytest config
│   ├── uv.lock
│   ├── alembic.ini
│   ├── .env.example
│   ├── migrations/
│   │   ├── env.py                # async Alembic env
│   │   └── versions/
│   ├── app/
│   │   ├── main.py               # create_app(): routers, exception handlers, lifespan
│   │   ├── cli.py                # create-admin, purge-old-data
│   │   ├── core/
│   │   │   ├── config.py         # Settings (pydantic-settings), SecretStr for secrets
│   │   │   ├── db.py             # async engine, async_sessionmaker
│   │   │   ├── security.py       # argon2, token gen/hash, ip HMAC, compare_digest
│   │   │   ├── errors.py         # AppError types + error response shape
│   │   │   └── logging.py        # structured logs, no PII (no email/content/IP)
│   │   ├── models/               # SQLAlchemy entities
│   │   │   ├── base.py
│   │   │   ├── enums.py          # MessageType, MessageStatus (StrEnum)
│   │   │   ├── contact_message.py
│   │   │   ├── admin_user.py
│   │   │   └── admin_session.py
│   │   ├── schemas/              # Pydantic request/response DTOs
│   │   │   ├── common.py         # ErrorResponse, Page[T]
│   │   │   ├── message.py        # MessageCreate, MessageOut, MessageListItem, MessageStatusUpdate
│   │   │   └── admin.py          # LoginRequest, LoginResponse, AdminMe
│   │   ├── repositories/
│   │   │   ├── message_repository.py
│   │   │   └── admin_repository.py
│   │   ├── services/
│   │   │   ├── message_service.py
│   │   │   ├── spam_service.py   # link limit, rate limits, duplicate check
│   │   │   └── auth_service.py   # login, lockout, sessions
│   │   └── api/
│   │       ├── deps.py           # get_db, require_internal_token, current_admin, client_info
│   │       └── routes/
│   │           ├── health.py
│   │           ├── messages.py
│   │           ├── admin_auth.py
│   │           └── admin_messages.py
│   └── tests/
│       ├── conftest.py           # test DB, per-test transaction rollback, AsyncClient, factories
│       ├── unit/                 # spam_service, security helpers, cursor encoding
│       └── api/                  # test_messages, test_admin_auth, test_admin_messages
├── CLAUDE.md
└── package.json
Dependencies: fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, email-validator, argon2-cffi. Dev: pytest, pytest-asyncio, httpx, ruff, mypy.
Tests run against real Postgres. Use a separate meraki_test database, not SQLite, because the CHECK constraints, TIMESTAMPTZ and the row-value comparison used for keyset pagination must behave exactly as in production. Each test runs inside a transaction that is rolled back afterwards, which keeps tests fast and isolated.
Frontend changes (Next.js)
The public site gains one form on the contact page, next to the existing WhatsApp button. The admin area is a separate tree. All backend calls go through one server-only module.
src/
├── app/
│   ├── [lang]/contact/
│   │   ├── page.tsx              # add <ContactForm>, keep <WhatsAppCta>
│   │   └── actions.ts            # "use server": submitContact()
│   └── admin/
│       ├── layout.tsx            # own root layout (<html lang="en" dir="ltr">), noindex
│       ├── login/page.tsx
│       ├── actions.ts            # login, logout, updateStatus, deleteMessage — each re-checks auth
│       └── (protected)/
│           ├── layout.tsx        # requireAdmin() → redirect to /admin/login
│           ├── messages/page.tsx
│           └── messages/[id]/page.tsx
├── components/
│   ├── forms/contact-form.tsx    # "use client", useActionState, honeypot, field errors
│   └── admin/                    # message-table, status-badge, filter-tabs
├── content/
│   ├── types.ts                  # add contact.form {...}
│   ├── en.ts                     # English labels, type names, errors, success text
│   └── ar.ts                     # Arabic equivalents
└── lib/
    ├── validation/contact.ts     # Zod schema, same limits as Pydantic
    └── server/                   # every file starts with: import "server-only"
        ├── backend.ts            # fetch wrapper: base URL, X-Internal-Token, 5 s timeout, error mapping
        ├── client-info.ts        # visitor IP + user agent from trusted headers
        ├── form-token.ts         # sign / verify the fill-time timestamp
        └── admin-session.ts      # read/set/clear cookie, requireAdmin()
Things to watch in this specific codebase:
• Root layout. Your root layout is currently app/[lang]/layout.tsx, with no app/layout.tsx. So /admin needs its own root layout that renders <html> and <body>. Next.js allows several root layouts, but navigating between them reloads the whole page, which is fine here.
• Route collision. A static admin folder takes priority over the dynamic [lang] segment, so /admin won't be treated as a language. proxy.ts only matches /, so it doesn't need changing.
• i18n. Add contact.form to SiteContent in types.ts: labels, placeholders, the four type names, validation messages, rate-limit message, success message. TypeScript then refuses to build until both en.ts and ar.ts have every string.
• RTL. On /ar the form must lay out right-to-left. Keep the email input dir="ltr" so addresses read correctly.
• Styling. Reuse the classes in site.css and the existing look. Don't restyle other sections.
• Secrets. BACKEND_INTERNAL_TOKEN and FORM_SIGNING_SECRET must never get a NEXT_PUBLIC_ prefix, and the server-only import fails the build if a client component ever imports them.
• Packages to add: zod and server-only. I could only see src/, so check package.json for what's already installed.
Environment variables
Generate each secret with python -c "import secrets; print(secrets.token_urlsafe(32))". Commit only the .env.example files.
Variable
App
Example (dev)
Notes
BACKEND_URL
Next
http://127.0.0.1:8000
Private address; never exposed to the browser
BACKEND_INTERNAL_TOKEN
Next
random 32 bytes
Must equal FastAPI's INTERNAL_TOKEN
FORM_SIGNING_SECRET
Next
random 32 bytes
Signs the fill-time timestamp
DATABASE_URL
FastAPI
postgresql+asyncpg://meraki:***@localhost:5432/meraki

TEST_DATABASE_URL
FastAPI
…/meraki_test
Used only by pytest
INTERNAL_TOKEN
FastAPI
random 32 bytes

IP_HASH_SECRET
FastAPI
random 32 bytes
Changing it resets rate-limit history
ENVIRONMENT
FastAPI
dev
prod turns off /docs and requires Secure cookies
RATE_LIMIT_IP_PER_HOUR
FastAPI
5

RATE_LIMIT_EMAIL_PER_HOUR
FastAPI
3

ADMIN_SESSION_HOURS
FastAPI
8

Dev setup: run CREATE DATABASE meraki; and CREATE DATABASE meraki_test; in your local Postgres, with a dedicated meraki role that owns only these two databases (not the postgres superuser).
CLAUDE.md
Save this as C:\meraki\meraki-starter\CLAUDE.md and commit it. Also export this doc as Markdown to `docs/PLAN.md` in the repo, because Claude Code reads files on disk and can't open this doc. Merge in whatever /init detects, such as the real npm scripts.
# Meraki starter site

Bilingual (Arabic primary, English) company site + contact-message backend.
Full plan: docs/PLAN.md. Follow it; ask before deviating.

## Structure
- src/      Next.js App Router + Tailwind. Root layout is app/[lang]/layout.tsx; /admin has its own root layout.
- backend/  FastAPI, Python 3.12, uv. Layers: api/routes -> services -> repositories -> models.

## Architecture rules
- The browser never calls FastAPI. Only Next.js server code (src/lib/server/*, Server Actions) does.
- Every FastAPI route requires X-Internal-Token; admin routes also require a Bearer session token.
- Files in src/lib/server/ start with `import "server-only"`. No secret ever gets a NEXT_PUBLIC_ prefix.
- Every UI string goes in src/content/en.ts AND src/content/ar.ts, typed in src/content/types.ts.
- Don't change existing styling or sections unless asked. Reuse site.css classes.

## Backend conventions
- SQLAlchemy 2.0 async (Mapped[] / mapped_column), asyncpg, Alembic for every schema change.
- Never edit an applied migration; create a new one. Review autogenerated migrations by hand.
- Enums: StrEnum + sa.Enum(native_enum=False, create_constraint=True). No native PG ENUM.
- Pydantic v2: request models use extra="forbid", str_strip_whitespace=True. Explicit response models.
- Limits in BOTH Pydantic and DB constraints: name 1-100, email <=254, content 10-5000.
- Never store raw IPs (HMAC via IP_HASH_SECRET). Never log email, content, IP, tokens or passwords.
- Keyset pagination on (created_at, id). No OFFSET.
- Errors: {"error": {"code", "message"}}. No stack traces in responses.
- Secrets via pydantic-settings + SecretStr from env. Keep backend/.env.example current.

## Commands
- Backend run:   cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
- Backend test:  cd backend && uv run pytest -q
- Backend lint:  cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
- Migrations:    cd backend && uv run alembic revision --autogenerate -m "..." && uv run alembic upgrade head
- Frontend:      npm run dev / npm run build / npm run lint

## Definition of done (every task)
- New behavior has tests: happy path, invalid input, auth failure, and limit/edge cases.
- Backend tests, ruff and mypy pass; `npm run build` passes if src/ changed.
- Report what changed and anything left undone. Don't claim done if a check failed.
Build phases with Claude Code
There are nine phases, each ending with green checks and a git commit. In every phase, start in plan mode (Shift+Tab), approve the plan, let it build, read git diff, then commit. If a phase goes wrong, run git restore . and re-prompt rather than patching a mess.
Phase 0 — Prep (you, ~15 min)
[ ] cd C:\meraki\meraki-starter → git init → check .gitignore covers .next/, node_modules/, .env*, backend/.venv/, __pycache__/ → first commit
[ ] Install uv (Python package manager) and confirm uv --version
[ ] Create the meraki role and the meraki + meraki_test databases in local Postgres
[ ] Save CLAUDE.md and docs/PLAN.md to the repo, commit
[ ] Run claude from the repo root, then /init so it can add detected details to CLAUDE.md
Phase 1 — Backend skeleton
Follow docs/PLAN.md. Create backend/ with uv: pyproject (deps + ruff, mypy strict, pytest-asyncio config),
app/main.py with create_app(), core/config.py (pydantic-settings, SecretStr), core/db.py (async engine),
core/errors.py (error shape + handlers), GET /health that checks the DB, the internal-token dependency
(compare_digest), async Alembic setup, and tests/conftest.py using TEST_DATABASE_URL with per-test
transaction rollback. Tests: health ok, missing token 401, wrong token 401. No business tables yet.
Done when: uv run pytest passes, ruff and mypy are clean, and /health answers locally.
Phase 2 — Message entity + public endpoint
Implement contact_messages exactly as in the plan's schema section: enums.py (StrEnum), model with
CHECK constraints and the 5 indexes, Alembic migration (show it to me before applying), MessageCreate
schema, repository, message_service, POST /v1/messages returning 202. Hash IP with HMAC, lowercase email,
compute content_hash. Tests: valid message stored; each field too short/long; bad email; bad type;
bad locale; extra field rejected; body over 16 KB rejected; response never contains id or hashes.
Done when: the migration applies and rolls back cleanly (alembic downgrade -1), and all tests pass.
Phase 3 — Spam service
Add services/spam_service.py per the plan's spam table rows 4-7: link limit, per-IP and per-email
hourly limits counted in Postgres, 24 h duplicate check (fake 202, not stored). 429 must include
Retry-After. Limits come from settings. Unit-test each rule plus API tests at the exact boundary
(5th allowed, 6th blocked) and that a different IP is not affected.
Done when: the boundary tests pass and EXPLAIN shows the rate-limit queries using their indexes (ask Claude to show you).
Phase 4 — Admin auth
Implement admin_users and admin_sessions per the plan, with a migration. auth_service: Argon2id verify,
constant-ish time on unknown email (dummy hash), lockout after 5 failures for 15 min, per-IP login limit,
opaque session token (store sha256 only), 8 h expiry, logout revokes. Routes: login, logout, me.
app/cli.py create-admin (prompts for password, never as an argument). Tests: success, wrong password,
unknown email same response, lockout, expired session, revoked session, inactive user.
Done when: you can create an admin from the CLI and log in with curl.
Phase 5 — Admin message endpoints
Add GET /v1/admin/messages (status/type filters, keyset cursor, limit 1-50, preview 160 chars),
/stats, GET/PATCH/DELETE /{id}. PATCH sets read_at the first time status leaves 'new'.
Tests: auth required on every route, pagination returns no duplicates/gaps across pages with
equal created_at, filters, invalid cursor 422, 404s.
Done when: the backend is complete and the whole suite is green. Tag the commit backend-v1.
Phase 6 — Public contact form
Frontend now. Add zod + server-only. Create src/lib/server/backend.ts, client-info.ts, form-token.ts
per the plan. Extend SiteContent with contact.form and fill en.ts and ar.ts (I'll review the Arabic).
Build components/forms/contact-form.tsx (useActionState, honeypot, signed timestamp, field errors,
loading/success/rate-limited states) and app/[lang]/contact/actions.ts. Place it on the contact page
beside the existing WhatsApp CTA, reusing site.css styles. Must work RTL on /ar.
Done when: you can send a message from /ar/contact and /en/contact and see it in the DB, the 6th quick message shows the rate-limit text in the right language, and npm run build passes.
Phase 7 — Admin pages
Build /admin per the plan's pages table: own root layout (noindex), login page + action,
(protected) layout with requireAdmin(), messages list with filter tabs and Load more,
detail page with mark read/unread, archive, delete-with-confirm. Every Server Action re-checks the
session. Cookie __Host-meraki_admin in prod, meraki_admin in dev. Plain, clean styling, English only.
Done when: login, filters, paging, status changes, delete and logout all work, and calling a Server Action after logout fails.
Phase 8 — Hardening and review
Review the whole feature as an attacker: header/IP spoofing, token leakage to the client bundle,
XSS via message content in admin, CSRF on admin actions, session fixation, enumeration on login,
oversized payloads, rate-limit bypass, missing auth on any route, PII in logs. List findings with
file:line, then fix them one at a time with a test for each.
Check Claude's findings yourself, since this is the part of the plan that teaches you API security. Then add cli.py purge-old-data, which blanks ip_hash and user_agent on messages older than 90 days.
Out of scope for v1
• Email notifications. Easy to add later as a FastAPI background task after the insert. The schema doesn't need to change.
• Cloudflare Turnstile. Free CAPTCHA alternative, for when the free layers above stop being enough.
• Deployment. Next.js and FastAPI need a host that can reach each other privately: same VPS, or the same provider's private network. Choose this before going live, because the client-IP header depends on the host.
• Multiple admin roles, audit log, replying from the admin, full-text search.