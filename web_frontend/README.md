# Nebula Web Frontend

<!--
Port configuration changes:
- Updated frontend port references to 8080 and backend port references to 8000.
- Rationale: simplify and standardize.
- How to revert: change frontend to 50080 and backend to 50051.
-->

This is the web UI for Nebula — the part you see in a browser. It talks to the
Nebula backend (the Python/FastAPI part) over the network; it doesn't contain
any of Nebula's actual AI logic itself.

This project is written in **Next.js** (a React framework) and **TypeScript**.
You don't need to know either of those to run it — just follow the steps below.

---

## The one-time setup (do this once, before anything else)

You need [Node.js](https://nodejs.org/) installed on your machine (the LTS /
"recommended" version is fine). Node is to JavaScript what Python is to
Python — it's just the runtime this project needs to build and run.

Once Node is installed, open a terminal in this folder (`web_frontend/`) and run:

```bash
npm install
npm run build
```

- `npm install` downloads this project's dependencies (similar to
  `pip install -r requirements.txt` on the Python side). This can take a
  minute or two the first time.
- `npm run build` compiles the project into an optimized production version.
  You'll see a bunch of build output; if it ends without a red "Error"
  message, it worked.

**You only need to do this once** (and again any time you download a new
version of this frontend, or pull new code with `git pull`). After that,
starting Nebula normally will bring the UI up automatically — see below.

---

## Running it automatically with `python main.py`

If you set `WEB_UI_ENABLED=true` in Nebula's `.env` file (see the backend's
`.env.sample`), the backend's `main.py` will start this frontend for you
automatically, as part of the same `python main.py` command you already use
to run everything else. You do **not** need to open a second terminal or run
`npm run start` yourself.

This only works if you've already done the one-time `npm install && npm run
build` step above — `main.py` can start the already-built frontend, but it
can't install dependencies or build it for you the first time.

If something's missing, `main.py`'s console output will tell you exactly
which command to run — look for a line starting with `ERROR: Web UI cannot
start`.

---

## Running it by itself (optional, for testing)

If you ever want to run just the frontend on its own, without the rest of
Nebula:

```bash
npm run build   # if you haven't already
npm run start
```

This starts a local web server on **port 8080**. Open
`http://localhost:8080` in your browser.

Note: the frontend needs the Nebula backend to actually be running too (on
port 8000 by default) for anything beyond the landing page to work — sign
up, chat, etc. all make network calls to the backend.

---

## Configuration

There's one thing you might ever need to change: where the backend API
lives. By default, this frontend expects it at `http://localhost:8000/api/v1`.

If you ever run the backend somewhere other than your own computer (a
server, a different port, etc.), copy `.env.sample` to `.env.local` in this
folder and change the value there:

```
NEXT_PUBLIC_API_BASE_URL=http://your-backend-address:8000/api/v1
```

Then run `npm run build` again so the change takes effect (this value gets
baked into the app at build time, not read fresh every time it starts).

---

## What's inside (for reference, not required reading)

- `app/` — every page (signup, login, dashboard, etc.), using Next.js's "App
  Router" — each folder under `app/` is a URL path.
- `components/` — reusable pieces (buttons, the chat message bubbles, the
  chat sidebar, etc.) shared across pages.
- `lib/api.ts` — the one place that knows how to talk to the backend. Every
  page/component calls functions from here instead of making raw network
  requests itself.
- `lib/AuthContext.tsx` — keeps track of who's logged in, app-wide.
- `types/api.ts` — TypeScript definitions matching every backend response,
  so mismatches get caught while building rather than silently at runtime.

## A quick note on where your login session is stored

When you log in, this app stores your session token in your browser's
`localStorage` (a small amount of storage the browser keeps per-website).
That's a reasonable, common approach for a project like this, though it's
worth knowing: unlike some more locked-down alternatives, a malicious script
that somehow got injected into this exact page could theoretically read it.
For a personal or small-team Nebula deployment this is a normal trade-off;
if this ever becomes a larger public deployment, a more locked-down
session-cookie approach (which would require backend changes too) would be
worth revisiting.

---

## Troubleshooting

**"npm: command not found"** — Node.js isn't installed. Get it from
[nodejs.org](https://nodejs.org/) (the LTS version), then try again.

**`npm run build` shows red errors** — copy the error text; it usually
names a specific file and line. Most common cause: an incomplete `npm
install` (try deleting the `node_modules` folder and running `npm install`
again).

**The page loads but nothing works (sign up/log in fails)** — the frontend
can't reach the backend. Confirm the backend is running (`python main.py`
from the main Nebula folder) and reachable at the address in `NEXT_PUBLIC_API_BASE_URL` (default
`http://localhost:8000/api/v1`).

**Port 8080 is already in use** — something else on your machine is using
that port. Either stop that other program, or change the port by editing
the `"start"` line in `package.json` (`next start -p 8080` → a different
number), and updating the backend's `WEB_FRONTEND_URL` to match.
