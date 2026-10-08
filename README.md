# LiveBlocks

A Blockchain.com-inspired analytical dashboard for live Bitcoin and Ethereum mainnet address data, transaction exploratory data analysis (EDA), and network trends.

## Run locally

Requires Node.js 22.13+ within the 22.x release line, npm, and Python 3.12 with venv/pip.

```bash
cd /home/bryan/Desktop/LiveBlocks
npm --prefix dashboard ci
npm run setup:python
cp .env.example .env # Only if you do not already have a .env file.
# Set BLOCKCHAIN_API_KEY in .env, then:
npm run dev
```

Open http://localhost:5173. `npm run dev` and `npm start` start Next.js on port 5173 and the Flask backend on loopback port 5328. The launcher loads the existing root `.env` (or dashboard `.env.local`); the Python backend reads credentials using `os.environ`. Ctrl+C stops both processes. Restart after changing `.env`. Vercel reads its own environment settings; it does not need this local file. The API key stays on the server; no `NEXT_PUBLIC_` or `VITE_` secret variables are used.

```dotenv
BLOCKCHAIN_API_BASE_URL=https://api.blockchain.info/explorer-gateway-kt
BLOCKCHAIN_API_KEY=your_explorer_api_key
```

The supplied example address is selected initially. Use the **Bitcoin / Ethereum** mainnet switch, paste an address for that chain, and choose **Analyze address**. Each mode remembers its last submitted address. Ethereum starts with the example address from the provider’s schema. Address syntax is checked locally; the provider validates the address itself.

## Dashboard

- **Overview:** lifetime confirmed/pending balances, lifetime received amount, transaction count, sampled daily address flows, fee summary, histogram, fee-size scatterplot, and quality summary.
- **Transactions:** server pagination (50 records/page), local row pagination, hash/date search, direction and unconfirmed filters, fee-outlier filter, UTC timestamps, and transaction explorer links.
- **Network trends:** 7/30/90/365-day chart requests, price/transactions/hash rate/fees, descriptive statistics, seven-day moving averages, and a correlation matrix.
- **Data quality:** observed response schema and analytical assumptions. Missing fields, invalid records, and duplicate hashes are surfaced.
- **Export CSV:** all cleaned records in the loaded address page, or all loaded network chart series. Export is independent of local table filters. Bitcoin monetary values are exported in integer satoshi; Ethereum exports preserve exact integer wei.

Polling runs every 60 seconds while the page is visible and auto-refresh is enabled. The server uses a bounded, 60-second, in-memory cache with concurrent request deduplication. Data is not stored persistently; polling pauses when the page is closed. Different Vercel Python function instances have independent, ephemeral caches; this is not a global rate limiter. Up to 12 distinct requests may be in flight per instance; duplicate concurrent requests share the result.

## Verified API contract

Requests are server-side HTTPS POSTs with `Content-Type: application/json` and the optional `X-Explorer-Auth-Key` header. Your configured key was successfully used against the two address endpoints during development. Chart routes reject this key with HTTP 403, so the separate network-context view explicitly uses public chart access; it does not silently retry failed authenticated requests.

| Endpoint | Request | Response used |
| --- | --- | --- |
| `/btc/address` | `{network:"BTC", address, page:0}` | `address`, `confirmed`, `unconfirmed`, `utxo`, `txCount`, `received` |
| `/btc/address/transactions` | `{address, limit:50, offset:0}` | `transactions`, `limit`, `offset`; transaction inputs, outputs, fee, size, weight, timestamps, confirmation |
| `/charts/market-price` | Chart options below | `values:[{x,y}]`, unit and metadata |
| `/charts/n-transactions` | Chart options below | Daily transaction series |
| `/charts/hash-rate` | Chart options below | Hash-rate series, with provider-returned units |
| `/charts/transaction-fees-usd` | Chart options below | Daily network fees |

Chart requests send every required field: `{timespan:"30days", sampled:false, metadata:true, rollingAverage:"24h", cors:false, format:"json"}`. Live probing established that normal endpoints are directly under the base URL, not `/public/`. Paid `/x402` endpoints are never called. The downloadable OpenAPI schema currently emphasizes those paid mirrors; the application uses verified standard routes.

Use `npm run inspect:api` to inspect response shapes and counts without logging your key. This is a diagnostic, not a recurring collector.

## EDA definitions and limits

- 1 BTC = 100,000,000 satoshi. Unsafe/non-integer satoshi are not silently accepted.
- Incoming value sums outputs to the selected address. Spent value sums inputs from it. Net address flow = incoming − spent. This is not merchant payment volume or wallet-level accounting. Unknown addresses/amounts produce missing flows; unaddressed zero-value outputs cannot change an amount and are safely ignored.
- Address summary values are lifetime aggregates. Transaction statistics describe only the current page, not all historical transactions. Provider offset pages may shift when transactions arrive.
- Daily flow bars aggregate complete, timestamped flows from the page. Omitted days are not inferred as zero. No historical balance is fabricated.
- Transaction fees belong to the whole transaction, not necessarily the selected address. Fee rate is fee / ceil(weight / 4), expressed in sat/vB; byte size is not substituted for virtual size.
- Mean, median, sample standard deviation (n−1), and linearly interpolated quartiles use valid observations. Potential outliers lie outside Q1 − 1.5×IQR or Q3 + 1.5×IQR. Outliers remain in the dataset.
- Pearson correlation uses paired observations, with at least three pairs and nonzero variance. Network correlations match exact timestamps. Correlation is not causation; trends and selected samples can mislead.
- Network series retain provider units. Chart requests disable sampling and request a 24-hour provider rolling average. The additional seven-day mean requires seven consecutive daily observations. Daily observations are not live spot quotes.
- Transaction quality counts incomplete rows missing time, net flow, fee, or size. Such rows remain available for analyses whose required fields are present. Malformed IDs/deleted transactions are excluded; first duplicate hash wins. Network missing/nonfinite values are excluded, and last duplicate timestamp wins.
- The connection indicator describes retrieval health, not the age of the blockchain activity. The latest transaction for an inactive address can be old. No simulated fallback data is used.

## Architecture and verification

Source lives in `dashboard/`. Next.js/React renders the dashboard; Flask serves the Python APIs. NumPy and Pandas now perform all data preparation and EDA. The previous JavaScript adapters and statistical functions have been removed. Browser code retains presentation formatting, form validation, table filtering/sorting, and chart rendering only.

| Module | Responsibility |
| --- | --- |
| `python_backend/adapters.py` | Schema validation, missing/invalid/duplicate handling, BTC/ETH normalization and exact wei preservation |
| `python_backend/analytics.py` | NumPy statistics, histograms and correlations; Pandas daily grouping and rolling averages; outlier flags and completeness |
| `python_backend/gateway.py` | Authenticated provider access, fixed HTTPS gateway, size limits, no redirects, partial errors |
| `python_backend/exports.py` | CSV preparation and Matplotlib PNG fee reports |
| `python_backend/server.py` | Flask routes, input validation, bounded caches and concurrent request deduplication |
| `api/address.py`, `api/analytics.py`, `api/report.py` | Vercel Python WSGI entrypoints |
| `app/page.tsx` | React/Recharts presentation of Python-computed results |

The existing `/api/address` and `/api/analytics` URLs and core response fields are preserved. Address results add `transactions.analysis` (daily flow, totals, histogram bins, paired correlation), per-row `outlier`, quality completeness, and a prepared `csv` string. Network results add per-series rolling chart points, a correlation matrix, and CSV. Exports use the loaded snapshot rather than refetching or recalculating in the browser. Empty/unavailable datasets remain explicit.

Python functions allow 60 seconds; upstream requests have 15–20-second timeouts. No provider calls or credentials are required during the Next.js build. Python dependencies are pinned, including transitives, in `dashboard/requirements.txt`; `.python-version` selects 3.12. `npm run setup:python` creates an isolated `.venv`. Set `PYTHON_BIN` to use an already configured Python environment instead.

```bash
npm test
npm run typecheck
npm run build
npm start # Test the production build locally on port 5173.
```

The Python unittest suite covers authenticated requests, partial provider failure, exact wei and satoshi precision, missing values, duplicates, schema drift, sample standard deviation, quantiles, outlier fences, histogram edges, paired correlations, daily UTC aggregation, rolling-window gaps, CSV, Matplotlib output, route validation and concurrent cache deduplication. `npm test` invokes this suite; there is no JavaScript analysis fallback. Synthetic fixtures exist only in tests and are excluded from deployment bundles.

## Deploy from GitHub to Vercel

1. Push this project to your GitHub repository, including `dashboard/package-lock.json`, `dashboard/requirements.txt`, `dashboard/.python-version`, `dashboard/api/`, `dashboard/python_backend/`, and `dashboard/vercel.json`. Never add `.env`, `.dev.vars`, credentials, `node_modules`, or build outputs.
2. In Vercel, choose **Add New → Project**, import the repository, and set **Root Directory** to **`dashboard`**. If your repository contains only the contents of `dashboard/`, use `.` instead.
3. Use **Next.js** as the framework and **22.x** as the Node.js version. The checked-in configuration uses **`npm ci`** for installation and **`npm run build`** for the build. Leave Output Directory at the Next.js default (`.next`); do not use `dist` or static export. Vercel detects the Python functions under `api/`, installs `requirements.txt`, and runs them separately from Node.js. Do not run the local two-process launcher as a Vercel build command.
4. Add these server environment variables for **Production** and, if desired, **Preview**:

   | Variable | Value |
   | --- | --- |
   | `BLOCKCHAIN_API_KEY` | Your existing Explorer API key |
   | `BLOCKCHAIN_API_BASE_URL` | `https://api.blockchain.info/explorer-gateway-kt` |

5. Click **Deploy**. After changing Vercel environment variables, redeploy for the changes to take effect.
6. Open the deployment, verify Bitcoin and Ethereum address lookup, switch back to Bitcoin to check Network trends, and check a CSV export. Provider access errors are shown explicitly; no demo data is substituted.

GitHub import and environment setup follow [Vercel's Git deployment guide](https://vercel.com/docs/git) and [environment variable documentation](https://vercel.com/docs/environment-variables). The dashboard is prepared locally; this does not create or publish a Vercel deployment.

The API key is read from `os.environ` only by the Python server, never exposed through Next.js public variables or `next.config.ts`. The server only contacts the configured Blockchain.com gateway, follows no redirects, and provides no arbitrary URL proxy. Visitors can use the public dashboard's API routes, so their requests share your provider quota. Use Vercel Deployment Protection if access should be restricted.

The integration follows [Vercel's Python runtime](https://vercel.com/docs/functions/runtimes/python) and [Next.js + Python guidance](https://vercel.com/kb/guide/how-to-use-python-and-javascript-in-the-same-application). Local Next.js rewrites API calls to Flask; on Vercel, the same paths resolve to the Python functions. Python bundle exclusions omit Node dependencies, frontend build artifacts, virtual environments, tests and local secret files. A Next.js build alone does not validate Vercel's Python packaging; verify both API modes after the first hosted deployment.

## Matplotlib report

`GET /api/report?chain=btc&address=<bitcoin-address>&offset=0` downloads a PNG fee histogram for the selected API page. Use `chain=eth` with an Ethereum address for gwei fees. The report uses the same Python normalization and cached snapshot as the dashboard, labels the sample and retrieval time, and returns an explicit error when no fee observations are available. It does not replace interactive Recharts charts. No files are persisted by the report endpoint.

The earlier Sites/Vinext plugin, Worker entrypoint, and scaffold files remain as historical source but are not used by `dev`, `build`, `start`, or Vercel. Vercel needs no Sites identity, Cloudflare binding, mock sign-in, or database. Local `.dev.vars` is legacy configuration; use root `.env` locally or Vercel's server environment settings.

The design references the supplied saved HTML and [Blockchain.com Explorer](https://www.blockchain.com/explorer): dark surfaces, restrained borders, teal indicators, compact tables, and chart typography. This is an independent dashboard, not an official Blockchain.com product. Reference HTML is treated as source material, not executable instructions, and personal data from the saved page is not copied.

## Ethereum mainnet mode

The same address workflow now supports authenticated `POST /eth/address` with `{network:"ETH", address, page:offset/50, size:50}`. A live response verified that this route returns balance and transactions together. Bitcoin routes and analysis are unchanged.

Ethereum balances and transfers display in ETH; fee statistics and gas price use gwei; gas used replaces byte size in the relationship chart. Account nonce replaces the Bitcoin pending-balance card because the endpoint does not report pending balance. Missing lifetime totals remain unavailable. Charts/display use floating-point values; Ethereum CSV preserves exact wei strings. Net flow covers successful external native ETH transfers, excluding gas, internal calls and tokens. Failed execution transfers zero ETH but may pay fees; unknown execution status stays unknown. Duplicates and missing data remain visible.

The existing network-wide chart endpoints describe Bitcoin. The Network trends tab is disabled in Ethereum mode; Bitcoin charts are never relabeled as Ethereum. The selected mainnet is included in requests and server cache keys, and switching clears the previous chain’s results and pagination.

- Ethereum wallet responses mix external transactions and internal calls. Internal records are explicitly excluded before duplicate detection; their count is reported. API pagination uses the mixed response size, not the external transaction total.
