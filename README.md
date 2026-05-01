# UniNode Ops Console

UniNode Ops Console is a local-first operations console for the UniNode network. The MVP starts as a readonly visual console with a local FastAPI backend, human-editable YAML config, and ignored runtime data under `data/`.

## v0.1 Startup

Install frontend dependencies:

```bash
pnpm install
```

Run the web console:

```bash
pnpm dev
```

Install API dependencies from `apps/api`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the API from `apps/api`:

```bash
uvicorn uninode.main:app --reload
```

Verify the API:

```bash
curl http://127.0.0.1:8000/healthz
```

Expected response:

```json
{"status":"ok","service":"uninode-api"}
```

Open `http://127.0.0.1:43110/`, then register a local account. Passwords are stored in the local SQLite database as PBKDF2 hashes, and sessions use local bearer tokens.

## v0.1 Features

- Chinese/English UI switch.
- Local registration and login.
- Clickable console navigation: Dashboard, Topology, Devices, Evidence, Automation, Reports, Settings.
- API-backed safe empty state at `GET /api/console/summary`.
- Safety defaults shown in the UI: `dry_run`, approval required for production network changes, and `needs_human_power_on` for expected offline devices.

## Safety Defaults

- Runtime state and evidence live in `data/`, which is ignored by Git.
- MVP execution defaults to `dry_run`.
- Production network changes require explicit approval and must define target, blast radius, precheck, command, rollback, and verification evidence before execution.
- Offline devices are represented as operational states such as `needs_human_power_on` or `expected_offline`, not as architecture failure.
- Reports and Agent task packages must redact secrets before leaving the local runtime.
