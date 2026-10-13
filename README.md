# clinic-mock — v1.0.0

This team's fork is `https://github.com/ducer37/clinic-callbot`. It tracks
mentor upstream `https://github.com/NgThVinh/clinic-mock` and keeps opt-in Week 2
seed records and synthetic WAV fixtures for the team's supervised demo.
The upstream code is not published back to the mentor repository.

**v1.0.0** — first stable release aligned to the **AI Health Residency product
contract, Rev 1.0** ([callbot-contract-site.vercel.app](https://callbot-contract-site.vercel.app/)).

FastAPI in-process; bearer-key auth with three recommended keys
(dev / test / prod); per-key tenant isolation; canonical contract fixtures
(`apt_00417`, `pt_3391`, `slot_91d2`, `cl_vinmec`) visible to every caller;
optional Langfuse tracing; `/_harness/*` test-scoping endpoints.

The full contract lives in [`docs/APIs.md`](docs/APIs.md) (authoritative human
spec) and [`docs/openapi.yaml`](docs/openapi.yaml) (machine-readable). The
contract itself is preserved verbatim in [`docs/product-contract.md`](docs/product-contract.md).

---

## Quickstart

```bash
# 1. Install
uv sync

# 2. Configure
cp .env.example .env  # or edit .env directly

# 3. Run (dev — hot reload)
uv run dev
# or production-style single process
uv run prod

# 4. Hit it
curl -s http://localhost:8000/health
# {"status":"ok"}

# 5. Browse the contract
open http://localhost:8000/docs
```

The first `uv run` resolves deps and installs the `dev` / `prod` console
scripts defined in `pyproject.toml`. `--reload` is automatic for `dev`.

---

## Authentication

Every request (except `/health`, `/docs`, `/openapi.json`, `/redoc`) needs a
bearer key:

```bash
curl http://localhost:8000/v1/patients?phone=0912345678 \
  -H "Authorization: Bearer $KEY"
```

Keys are registered in `.env`. The recommended layout is three named keys
covering the typical dev/test/prod split — each one becomes its own tenant
scope, fully isolated from the others:

```env
MOCK_API_KEYS=dev:sk_dev_replace_me,test:sk_test_replace_me,prod:sk_prod_replace_me
```

| Key | Use |
|---|---|
| `dev` | Local development, fixtures you don't mind losing. |
| `test` | CI / shared test environment. |
| `prod` | Any environment where data must survive a restart. |

Each key resolves to one isolated data scope, auto-derived as
`t_<sha256(key)[:8]>` — stable across restarts, opaque, unique per key.
The platform picks the scope; you don't configure it. Cross-tenant access
returns `404 NOT_FOUND` (existence hidden). Entries missing the `sk_` prefix
are silently dropped. No expiry, no rotation — keys live as long as they're
in the env.

The bare-key form (`MOCK_API_KEYS=sk_dev_xxx,sk_test_xxx`) still works if
you don't want the named scope; the auto-derived scope id just becomes
opaque.

---

## Observability

When `LANGFUSE_TRACES_ENABLED=true` (default) and
`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` are set, every
incoming request emits an OTel span to Langfuse with attributes documented in
[`docs/APIs.md` §14](docs/APIs.md#14-observability--langfuse-traces).

Disable for offline tests:

```env
LANGFUSE_TRACES_ENABLED=false
```

Spans are dropped, not buffered.

---

## Deployment

### Recording profile with reserve cases (team fork only)

For the video planned early on 14 October 2026, use this exclusive profile:

```env
MOCK_RECORDING_FIXTURES=1
MOCK_RECORDING_BASE_DATE=2026-10-14
MOCK_WEEK2_FIXTURES=0
MOCK_BOOKING_FIXTURES=0
```

It replaces the default data only while enabled: **five patients, five SCHEDULED
appointments, seven available slots**, all in `cl_vinmec` (+07:00).

| Appointment | Patient / DOB | Original time | Department |
| --- | --- | --- | --- |
| `apt_00417` | Nguyễn Tuấn Đức / 2000-07-31 | 15:30 | Nội tổng quát |
| `apt_eval_07` | Lê Thị Mỹ Linh / 1990-01-09 | 16:30 | Cơ xương khớp |
| `apt_eval_03` | Nguyễn Thị Mai / 1985-04-12 | 09:30 | Da liễu |
| `apt_eval_05` | Trần Văn Nam / 1972-11-03 | 10:30 | Nội tổng quát |
| `apt_eval_09` | Phạm Minh Anh / 1985-04-12 | 11:30 | Tai Mũi Họng |

Linh and the three reserve identities come from the existing Week 2 patient
fixtures. Their recording appointments use the common base day/clinic.
Available clocks on D: **09:00, 10:00, 14:00, 14:30, 15:00** (30 minutes each).
D+1 and D+2 have no free slot; D+3 has **09:00, 14:30**. `slot_91d2` retains
15:00 on D for the two primary scripts. No free/occupied intervals overlap,
and there are no duplicate capacities at the same clock. GET /slots still
returns legitimately released slots; reset between independent recordings.

All five patients use the existing **synthetic** phone hint `0912345600`, not
their real number. Lookup returns five candidates; full name plus DOB must
still select one. Mai and Minh Anh deliberately share a DOB but have different
names, so DOB alone cannot identify them. The primary callers remain Đức/Linh.
Keep gateway selector order `apt_00417,apt_eval_07,apt_eval_03,apt_eval_05,apt_eval_09`.
All aliases are already in the voice-worker allowlist.

Startup, `/_harness/seed` and `/_harness/reset` load the same profile. Those
endpoints do not accept arbitrary seed JSON. Deploy an image with this source
before enabling the flag on the team's AWS mock. Normal mentor/canonical data
is unchanged when the flag is off. Never enable the profile on scoring Mock.
Week 2/booking flags must be off, otherwise seed fails before replacement.

Blank `MOCK_RECORDING_BASE_DATE` uses tomorrow locally at seed/reset; pin the
date for this recording so crossing midnight does not move the schedule.
Use explicit dates in caller scripts. On a later recording day, choose a
future base date rather than moving the bot clock.

Preview the dataset without mutating a server:

```powershell
python -m clinic_mock.recording_fixtures
```

Use new call IDs/idempotency keys after reset; reset does not clear the
upstream API's separate replay cache. This is video demo data, not QC gold.

### Compact team QC scheduling profile

Use `MOCK_BOOKING_FIXTURES=0` for the team's compact demo/QC profile. The existing
canonical seed exposes only `slot_91d2`, 15:00–15:30 on 14 October 2026 in
`cl_vinmec`; there is no free slot in that clinic on 15 October. This profile
uses existing API/seed behavior and does not change the mentor's contract.
Keep `MOCK_BOOKING_FIXTURES=1` for the separate extended regression profile.

These are initial seed conditions: booking consumes the slot, rescheduling
releases the old slot, and reset/restart restores seed. Use a disposable mock
per test suite and reset between independent calls. Do not filter or remove
legitimately released slots during GET /slots. Fixed canonical dates must be
replaced through reviewed test data when expired, not by moving the bot's clock.

### Optional local Week 2 benchmark records

For the callbot benchmark only, `MOCK_WEEK2_FIXTURES=1` adds eight synthetic
patients and eleven appointments to the canonical fixture. The flag is off by
default. Both startup and `/_harness/reset` recreate the same records; the
existing `/_harness/seed` endpoint still has no request body. Use a dedicated
local instance because the benchmark resets the mock before every case:

```powershell
$env:MOCK_WEEK2_FIXTURES='1'
$env:MOCK_API_KEYS='sk_eval_week2'
.\.venv\Scripts\python.exe -m uvicorn clinic_mock.app:app --host 127.0.0.1 --port 8010
```

Fixture IDs and values are in `src/clinic_mock/week2_fixtures.py`. They are for
demo/evaluation and do not change the mentor scoring fixture when the flag is
unset.

The team's AWS demo also enables this flag. State lives in process memory:
restart/redeploy and `POST /_harness/reset` discard runtime data and recreate
the seed records. Reset restores their configured status/version/attempt count;
records created through APIs but absent from the seed, snapshots and writelog
are removed. Reset affects the entire store, not only the selected appointment.
The callbot frontend's **Reset dữ liệu Mock** proxies this endpoint; it does
not hold a separate copy of the fixtures.

---

A `Dockerfile` ships in the repo (builder + runtime stages, non-root user,
uv-managed venv). The runtime image respects `PORT` (Vercel convention) over
`APP_PORT`:

```bash
docker build -t clinic-mock .
docker run -p 8000:8000 --env-file .env clinic-mock
```

On Vercel the build reads `PORT=80` from the platform; locally it falls back
to `APP_PORT=8000` (or the default `8000`).

### Optional HTTP audio fixtures

`APP_ENABLE_AUDIO_FIXTURES=true` exposes two public, synthetic development clips:

- `/test-fixtures/audio/caller_name.wav`
- `/test-fixtures/audio/caller_dob.wav`
- `/test-fixtures/audio/manifest.json`

The flag is off by default. These endpoints only host immutable caller WAV files;
they do not read or mutate appointment state and are separate from both `/v1` and
`/_harness`. Do not enable them on the mentor's official scoring image.

### Optional inbound booking fixtures (team demo only)

`MOCK_BOOKING_FIXTURES=1` adds twelve available slots and one occupied booking
without changing canonical records or API behavior. It is disabled by default
and can coexist with `MOCK_WEEK2_FIXTURES=1`. Dedicated providers and stable
`slot_booking_*` / `apt_booking_*` IDs keep these intervals separate from
canonical/Week 2 appointments. Fixtures use 15-minute appointments; this is
test data, not a contract requirement about consultation duration.

The existing demo **Reset dữ liệu Mock** button already calls `/_harness/reset`.
Startup, `/_harness/seed` and reset all load the enabled pack through
`seed_default()`. No frontend changes or custom seed request body are needed.
These operations discard runtime data for the entire instance: use a dedicated
demo/test mock, and reset between calls rather than during an active call.

Configuration can be set in `.env` or process environment (environment wins):

```powershell
$env:MOCK_BOOKING_FIXTURES='1'
$env:MOCK_API_KEYS='sk_booking_disposable'
$env:LANGFUSE_TRACES_ENABLED='false'
# Leave unset/empty for demo, or pin a future first date for repeatable tests:
$env:MOCK_BOOKING_BASE_DATE=''
.\.venv\Scripts\python.exe -m clinic_mock.booking_fixtures
.\.venv\Scripts\python.exe -m uvicorn clinic_mock.app:app --host 127.0.0.1 --port 18081
```

With no fixed date, **D** is tomorrow in UTC+07:00, computed once at each
startup/seed/reset. A pinned `MOCK_BOOKING_BASE_DATE=YYYY-MM-DD` makes the seed
repeatable; choose a future date for actual bot calls. The manifest command
prints the planned dates without changing state; `/_harness/state` is the truth
for the running instance, especially if it was seeded before midnight.

| Window | Available data / expected use |
| --- | --- |
| D, 09:00–11:00 | Six free slots: 09:00, 09:15, 09:45, 10:00, 10:15, 10:30. Exercise multiple offers and more choices. |
| D, 09:30 | Occupied by `apt_booking_busy_0930`; absent from GET slots. Bot searches the same morning and first offers 09:15, 09:45, 09:00; MORE then offers 10:00, 10:15, 10:30. |
| D, 11:00–12:00 | One exact slot at 11:30. |
| D, 12:00–18:00 | Three slots at 14:00, 14:30, 15:00. Switch from morning to afternoon while retaining D. |
| D+1, 13:30–14:30 | One slot at 14:00. |
| D+2, 09:00–10:00 | Two slots at 09:00 and 09:30. |
| D+3, 17:00–18:00 | No slot; use this window rather than assuming the entire day has no legacy fixtures. |
| D+4, 07:00–07:15 | 07:00 at `cl_vinmec` (00:00 UTC); separately, 09:00 at `cl_booking_other` to check clinic filtering. |

The inbound demo caller remains canonical: phone `0912345600`, name
`Nguyễn Văn A`, DOB `1978-03-14`, clinic `cl_vinmec`. All identities are synthetic.
The busy appointment belongs to a separate synthetic patient
`pt_booking_competitor`. For a race test, first discover a free slot, then book
it for this patient using POST `/v1/appointments` with a fresh Idempotency-Key
before the bot's confirmation. The bot must handle the unavailable slot and
obtain new consent; static busy fixtures alone do not test this race.

Reset restores patient/slot/appointment data, snapshots and writelog, but the
upstream routes keep a separate idempotency cache outside Store. Use a new key
and call ID for each independent run. Keep the same key/payload only when
testing retries within one run. This pack does not change upstream cache
semantics or add `/_harness/version`; it is not the official scoring image.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_booking_fixtures.py -q
```
