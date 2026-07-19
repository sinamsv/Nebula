/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // We intentionally do NOT hardcode the API URL here — it's read at
  // runtime from process.env.NEXT_PUBLIC_API_BASE_URL (see lib/api.ts).
  // NEXT_PUBLIC_* vars are inlined at build time by Next.js itself,
  // which is why .env.production.sample documents this one clearly.
};

export default nextConfig;
