# LiveBlocks dashboard

Next.js/React/Recharts frontend with a Flask Python backend. NumPy and Pandas own data preparation and EDA; Matplotlib generates downloadable fee-report PNGs. Bitcoin/Ethereum address workflows and the dark interface are preserved.

## Local setup

Requires Node.js 22.x, npm and Python 3.12 with venv/pip.

```bash
npm ci
npm run setup:python
# Copy .env.example to .env.local and configure the key and base URL.
npm run dev
npm test
npm run typecheck
npm run build
npm start
```

The launcher starts Next.js on port 5173 and Flask on loopback port 5328 and stops both on Ctrl+C. The parent workspace `.env` is also supported. `PYTHON_BIN` can select a custom Python environment. Build first before `npm start`. Vercel executes Python directly; the local Flask development server is never deployed as a long-running service.

## Vercel import

- Root Directory: `dashboard` in the full repository, or `.` for this directory on its own.
- Framework: Next.js; Node.js: 22.x; Python: 3.12 via `.python-version`.
- Install: `npm ci`; Build: `npm run build`; default Next.js output directory.
- Commit `requirements.txt`, `.python-version`, `api/`, `python_backend/` and `vercel.json`. Vercel installs Python requirements for the functions.
- Set `BLOCKCHAIN_API_KEY` and `BLOCKCHAIN_API_BASE_URL=https://api.blockchain.info/explorer-gateway-kt` in Vercel for Production and any required Preview deployments. Redeploy after changes.
- Never commit `.env`, `.env.local`, `.dev.vars`, `.venv`, credentials, or generated outputs. The blank `.env.example` is safe.

`/api/address` and `/api/analytics` are Python endpoints, returning normalized observations and computed EDA. Browser code only formats, filters, sorts and renders these results. CSV is prepared in Python from the same loaded snapshot. `/api/report?chain=btc&address=<address>&offset=0` downloads a Matplotlib PNG; use `chain=eth` for an Ethereum address. No mock fallback is present.

The Python backend keeps API keys in `os.environ`, uses only the HTTPS Blockchain.com gateway without redirects or paid x402 routes, and maintains a 60-second per-instance cache. Lifetime cards and page-level statistics remain separate. Ethereum exports retain exact wei; charts use floating-point ETH/gwei. Network trends remain Bitcoin-only.

The old Sites/Cloudflare files are inactive scaffolding. No database, Redis, external Python service, or separate Vercel project is required. See the parent README/HISTORY for methods and verification. See [Vercel Python documentation](https://vercel.com/docs/functions/runtimes/python) for packaging; a hosted deployment still needs an end-to-end check after import.
