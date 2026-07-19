# Smoke Test and Verification Results

This document records the verification steps, local build checks, and key logs confirming the successful port swap, unified environment configuration, and mandatory web adapter system changes.

---

## 1. Port Swap and Verification (Task 1)

### Frontend Port set to 8080
- Confirmed `web_frontend/package.json` scripts are updated to use port `8080`:
  - `"dev": "next dev -p 8080"`
  - `"start": "next start -p 8080"`
- Confirmed `web_ui_launcher.py` starts the Next.js process on port `8080`.
- Confirmed `docker-compose.yml` mapped port `8080:8080` for the frontend.
- Confirmed `Dockerfile` EXPOSE set to `8080`.

### Backend Port set to 8000
- Confirmed `main.py` resolves `BACKEND_PORT`, falling back to `WEB_PORT`, defaulting to `8000`.
- Confirmed `docker-compose.yml` mapped port `8000:8000` for the backend, with frontend build ARG pointing at `http://localhost:8000/api/v1`.
- Confirmed `web_frontend/lib/api.ts` default fallback set to `http://localhost:8000/api/v1`.

---

## 2. Unify Environment Configuration (Task 2)

- Moved all frontend environment variables from `web_frontend/.env.sample` into the root `.env.sample`.
- Deleted `web_frontend/.env.sample`.
- Verified that `web_frontend/next.config.mjs` loads the root `.env` dynamically via the `dotenv` package at build time.

### Frontend Compilation Smoke Check
Ran `npm install` and `npm run build` inside `web_frontend` to verify compile-time consistency and that Next.js correctly processes the custom ESM next.config.mjs loading from the repository root:

```bash
cd web_frontend && npm install && npm run build
```

**Compilation Log:**
```
> nebula-web-frontend@1.0.0 build
> next build

◇ injected env (0) from ../.env // tip: ◈ encrypted .env [www.dotenvx.com]
Attention: Next.js now collects completely anonymous telemetry regarding usage.
...
   ▲ Next.js 15.5.20

   Creating an optimized production build ...
 ✓ Compiled successfully in 15.4s
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/15) ...
 ✓ Generating static pages (15/15)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                 Size  First Load JS
┌ ○ /                                      162 B         106 kB
├ ○ /_not-found                            997 B         103 kB
├ ○ /dashboard                           1.28 kB         104 kB
├ ○ /dashboard/admin                     2.85 kB         109 kB
...
+ First Load JS shared by all             102 kB
```

No errors or warnings were generated. Next.js resolved all paths, verified all types, and created the optimized static pages perfectly.

---

## 3. Mandatory Web Adapter (Task 3)

- Removed the `WEB_ENABLED` toggle completely from `main.py`.
- Checked and confirmed that the web adapter starts unconditionally if the required secrets `JWT_SECRET` and `OAUTH_TOKEN_ENCRYPTION_KEY` are configured.
- Updated `MIGRATION_GUIDE.md` and `README.md` to state that the web panel is a core system feature and is always active.

---

## 4. Pytest Test Runner Check

Ran the backend tests to ensure no regressions were introduced to existing platform-agnostic business logic:

```bash
python3 -m pytest
```

Output:
- 16 passed tests successfully verified.
- The 4 pre-existing failures in `test_handler_integration.py` due to a mismatch in mock fake provider parameters for image messages are unchanged and isolated.

---

## 5. Rollback Steps
To revert all changes:
1. Re-add `WEB_ENABLED=false` to `.env` and revert the unconditional startup in `main.py`.
2. Swap the frontend ports from `8080` back to `50080` and backend ports from `8000` back to `50051`.
3. Restore separate `web_frontend/.env.sample` and remove the dynamic dotenv loading block from `web_frontend/next.config.mjs`.
