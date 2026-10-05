# LiveBlocks

A Blockchain.com-inspired analytical dashboard for live Bitcoin address data, transaction exploratory data analysis (EDA), and network trends.

## Run locally

Requires Node.js 22.13+ and npm.

```bash
cd /home/bryan/Desktop/LiveBlocks
npm --prefix dashboard install
cp .env.example .env # Only if you do not already have a .env file.
# Set BLOCKCHAIN_API_KEY in .env, then:
npm run dev
```

Open the local URL printed by the server. Restart after changing `.env`. `scripts/prepare-env.mjs` copies only the two allowed configuration values into the ignored `dashboard/.dev.vars` with restrictive permissions. The API key stays on the server; no `NEXT_PUBLIC_` or `VITE_` secret variables are used.

```dotenv
BLOCKCHAIN_API_BASE_URL=https://api.blockchain.info/explorer-gateway-kt
BLOCKCHAIN_API_KEY=your_explorer_api_key
```

The supplied example address is selected initially. Paste another Bitcoin mainnet address and choose **Analyze address** to inspect it. Address syntax is checked locally; the provider validates the address itself.

## Dashboard

- **Overview:** lifetime confirmed/pending balances, lifetime received amount, transaction count, sampled daily address flows, fee summary, histogram, fee-size scatterplot, and quality summary.
- **Transactions:** server pagination (50 records/page), local row pagination, hash/date search, direction and unconfirmed filters, fee-outlier filter, UTC timestamps, and transaction explorer links.
- **Network trends:** 7/30/90/365-day chart requests, price/transactions/hash rate/fees, descriptive statistics, seven-day moving averages, and a correlation matrix.
- **Data quality:** observed response schema and analytical assumptions. Missing fields, invalid records, and duplicate hashes are surfaced.
- **Export CSV:** all cleaned records in the loaded address page, or all loaded network chart series. Export is independent of local table filters. Monetary address values are exported in integer satoshi.

Polling runs every 60 seconds while the page is visible and auto-refresh is enabled. The server uses a bounded, 60-second, in-memory cache with concurrent request deduplication. Data is not stored persistently; polling pauses when the page is closed. Different Worker instances have independent caches.

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

Source lives in `dashboard/`: React/Vinext, Recharts, Lucide icons, Cloudflare Worker-compatible API routes. Pure adapters and EDA functions live in `dashboard/lib/*.mjs`; they can also be used from Node scripts.

```bash
npm test
npm run typecheck
npm run build
```

Tests cover authenticated request construction, partial provider failure, satoshi precision, missing values, duplicate handling, response drift, sample standard deviation, quantiles, outlier fences, constant data, histogram counts, paired correlations, and rolling-window gaps.

## Hosting and secrets

The project includes a private Sites hosting identity in `dashboard/.openai/hosting.json`. Hosted runtime configuration is separate from `.env`; configure the same base URL and API key as server environment values. Never commit `.env`, `.dev.vars`, raw private responses, or credentials. Source archives and browser bundles must exclude the key. The server only contacts the configured Blockchain.com gateway, follows no redirects, and provides no arbitrary URL proxy.

The design references the supplied saved HTML and [Blockchain.com Explorer](https://www.blockchain.com/explorer): dark surfaces, restrained borders, teal indicators, compact tables, and chart typography. This is an independent dashboard, not an official Blockchain.com product. Reference HTML is treated as source material, not executable instructions, and personal data from the saved page is not copied.
