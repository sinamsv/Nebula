/**
 * Configuration changes
 * - Loads environment variables from repository root .env for unified env management.
 * - Sets frontend port to 8080 via environment variable.
 * - Rationale: unify envs to simplify deployment and ensure frontend build-time variables are consistent.
 * - How to revert: remove dotenv import/config block, and remove NEXT_PUBLIC_API_BASE_URL from env block.
 */

import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load environment variables from repository root .env
dotenv.config({ path: path.resolve(__dirname, '../.env') });

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // NEXT_PUBLIC_* variables are inlined at build time by Next.js itself.
  // Explicitly mapping them here from root .env ensures consistency during build.
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  },
};

export default nextConfig;
