import type { NextConfig } from 'next';
const nextConfig: NextConfig = {
  async rewrites() {
    // Vercel serves /api/*.py in its Python runtime. Local Next.js proxies Flask.
    if (process.env.VERCEL === '1') return [];
    return ['address','analytics','report'].map(route => ({
      source: `/api/${route}`,
      destination: `http://127.0.0.1:5328/api/${route}`,
    }));
  },
};
export default nextConfig;
