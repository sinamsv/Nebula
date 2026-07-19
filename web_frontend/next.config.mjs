/**
 * Railway / PaaS single-port proxy (v1.6.1):
 * - Added rewrites(): every request to /api/v1/* made against Next.js's OWN
 *   origin (whatever public port/domain Railway gives it) is transparently
 *   forwarded, server-side, to FastAPI running INTERNALLY on
 *   127.0.0.1:BACKEND_PORT inside the same container. The browser never
 *   talks to FastAPI directly and never sees its internal port.
 * - This is what makes it possible for Railway's single public port to
 *   serve both the API and the UI without a second Railway service or an
 *   nginx layer in front of both.
 * - Because of this, NEXT_PUBLIC_API_BASE_URL should now normally be left
 *   as a relative path ("/api/v1") rather than a full "http://host:port"
 *   URL -- see .env.sample and web_frontend/lib/api.ts's default. A full
 *   absolute URL still works fine for local/non-proxied setups if you
 *   genuinely want the browser to hit FastAPI directly (e.g. running the
 *   frontend and backend as two separate processes/ports locally without
 *   Docker), since rewrites() only intercepts requests aimed at Next.js's
 *   own origin.
 * - How to revert: remove the rewrites() block below and go back to
 *   pointing NEXT_PUBLIC_API_BASE_URL at a full "http://host:8000/api/v1" URL.
 *
 * (Pre-existing) Configuration changes:
 * - Loads environment variables from repository root .env for unified env management.
 * - Sets frontend port to 8080 via environment variable (local/non-PaaS default only --
 *   see main.py's _resolve_public_port(), which PORT overrides on PaaS).
 */

import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load environment variables from repository root .env
dotenv.config({ path: path.resolve(__dirname, '../.env') });

// Where FastAPI actually listens INSIDE the container -- never exposed
// publicly since v1.6.1 (see main.py's _start_web_adapter(), which binds
// to 127.0.0.1 specifically). Mirrors main.py's own BACKEND_PORT/WEB_PORT
// fallback chain so the two stay in sync without hardcoding the port twice.
const INTERNAL_BACKEND_PORT = process.env.BACKEND_PORT || process.env.WEB_PORT || '8000';
const INTERNAL_BACKEND_URL = `http://127.0.0.1:${INTERNAL_BACKEND_PORT}`;

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // NEXT_PUBLIC_* variables are inlined at build time by Next.js itself.
  // Explicitly mapping them here from root .env ensures consistency during build.
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  },
  async rewrites() {
    return [
      {
        // Matches /api/v1/anything -- forwarded server-side to FastAPI's
        // own /api/v1/anything on the internal port. FastAPI's routes are
        // ALL already prefixed with /api/v1 (see web_backend/routes/*.py's
        // router = APIRouter(prefix="/api/v1/...")), so no path rewriting
        // beyond the host swap is needed.
        source: '/api/v1/:path*',
        destination: `${INTERNAL_BACKEND_URL}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
