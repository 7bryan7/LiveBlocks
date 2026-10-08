# History

## 2026-10-05 — Initial implementation

- Created the project README, contributor instructions, and change history.
- Inspected the supplied Explorer HTML for UI styling without executing it or copying saved account details.
- Inspected the Explorer Gateway OpenAPI schema and live responses; verified standard POST routes, required chart parameters, and the `X-Explorer-Auth-Key` header.
- Successfully authenticated the supplied `/btc/address` request after the user configured `.env`. Observed aggregate balances and counts, rather than assuming transaction time-series data were included.
- Verified `/btc/address/transactions` with a 50-row response and implemented address-focused EDA with explicit sample scope.
- Added address search, balance cards, daily flow charts, fee distribution, sample statistics, IQR outliers, fee-size correlation, filters, pagination, CSV export, response schema, and quality reporting.
- Added network context charts for price, transaction count, hash rate and USD fees, with selectable windows, seven-day means, and timestamp-aligned correlations.
- Added server-side API access, bounded caches, timeout/error handling, secret-safe diagnostics, and `.env` setup.
- Verified all 50 transaction records normalize correctly, including zero-value OP_RETURN outputs without addresses.
- The provided key is accepted on address endpoints but returns HTTP 403 on chart routes. Network charts explicitly use public access, separately from authenticated address data.
- Verified authenticated summary + 50 transactions, and all four public network series with 30 valid daily points each.
- Fixed Worker compatibility by rejecting redirects with manual redirect handling.
- Validation: 14 analytical/API tests pass; TypeScript check passes; production Worker/client build succeeds. Browser checks confirmed authenticated data, filters, and row pagination.
- Browser checks confirmed 7-day live network charts, correlation values, response schema, connection details, and no document overflow at a 390px mobile viewport.
- Source/browser build secret scan found no API-key copies. CSV serialization tests pass; the in-app browser did not expose a download event.
- Private hosting was prepared with a server secret, but publication was not completed because source-upload permission was declined. The working local preview remains available.

## 2026-10-05 — Bitcoin / Ethereum mainnet switch

- Added a two-mode mainnet switch while retaining the address workflow, existing layout, and Bitcoin behavior.
- Verified the authenticated Ethereum address response, including wei strings, external transactions, pagination and gas fields. Ethereum requests use `/eth/address`; API keys remain server-only.
- Added ETH/gwei/gas labels, Ethereum transaction links, account nonce, exact-wei CSV exports, and handling of failed/unknown transaction execution.
- Separated requests and caches by chain, canceled old in-flight work on switches, and preserved each chain’s last submitted address.
- Bitcoin-only Network trends is disabled in Ethereum mode. No new provider or fabricated Ethereum network data was added.
- Added regression tests for wei precision, fees, self-transfers, failures, missing data, duplicates, authentication, and Ethereum pagination.

- Ethereum wallet responses mix external transactions and internal calls. Internal records are explicitly excluded before duplicate detection; their count is reported. API pagination uses the mixed response size, not the external transaction total.
- Validation: authenticated Ethereum pages 0 and 1 load; round-trip mainnet switching restores chain-specific addresses and resets pagination. Mobile layout checked at 390px with no document overflow. Bitcoin baseline, Ethereum regression tests, TypeScript, and production build pass.

## 2026-10-05 — Vercel deployment preparation

- Changed the active development, build, and production commands from Vinext/Workers to standard Next.js on Node.js 22.x. The address workflow, analysis, and design are retained.
- Converted both API routes to server-only `process.env` configuration, explicitly dynamic Node.js execution, and 30-second Vercel function duration. Existing provider timeouts and real-data error behavior remain unchanged.
- Added `dashboard/vercel.json`, a Node version file, and a blank dashboard environment example. Updated setup instructions, contributor guidance, and Git ignore rules for deployment artifacts and local credentials.
- Kept the former Sites plugin and Worker entrypoint as inactive historical scaffold, excluded from application typechecking. Vercel does not require their hosting identity, Cloudflare bindings, mock authentication, or a database.
- Documented GitHub import with Root Directory `dashboard`, Next.js preset, `npm ci`, and the two server environment variables. Vercel caches are ephemeral per instance; there is no persistent collector or global quota limiter.
- Validation: analytical/API tests, TypeScript check, and Next.js production build pass. npm clean-install dry run validates the lockfile. The production server returned authenticated Bitcoin (50 rows), Ethereum (22 external rows), and all four live network series; malformed addresses/ranges return HTTP 400.
- Browser check: production Bitcoin renders with real data; Ethereum switching connects with no browser errors. Scanned 22 browser build assets for the configured API key: none found. Active route dependency traces exclude Sites bindings and local secret files.
- Build verification required running outside the local sandbox because it blocked Next.js subprocess output and localhost access. No Vercel deployment, GitHub push, or external source upload was performed; the user will import the repository and set runtime secrets in Vercel.

## 2026-10-08 — Python data preparation and EDA

- Replaced the JavaScript response adapters and EDA functions with a Flask/Python backend using NumPy and Pandas. Removed the old JavaScript analysis modules and Node API route implementations; there is no JavaScript analytical fallback.
- Python now owns BTC/ETH normalization, quality reporting, exact wei preservation, sample statistics, IQR flags, fee histograms, timestamp-paired Pearson correlations, daily UTC aggregation, consecutive-day rolling means, sample totals and CSV preparation. React/Recharts retains rendering, formatting and table controls.
- Preserved the existing address and network API paths and core response fields, including partial failures, provider authentication, source timestamps, limits and units. Added computed analysis payloads and prepared CSV to the responses.
- Added Matplotlib PNG fee reports at `/api/report`, using real normalized observations and explicit unavailable-data errors. Report generation is headless and serialized for thread safety.
- Added Python 3.12 Vercel entrypoints, pinned requirements, function bundle exclusions, an isolated local virtual environment, and an npm launcher that starts/stops both Next.js and loopback Flask. The API key stays in Python server environment variables.
- Replaced the JS adapter tests with 27 Python regression tests covering analytical methods, precision, missing/invalid/duplicate data, contracts, errors, strict JSON, exports and concurrent cache deduplication.
- Captured seven real provider responses outside the repository and compared Python with the original JS results: BTC summary/transactions, Ethereum, and four Bitcoin network series all matched, including histogram bins, daily flows, totals, correlations and rolling means within floating-point tolerance.
- Validation: `npm test` (27 tests), `npm run typecheck`, and the Next.js production build pass. Live checks returned 50 BTC rows, 23 external ETH rows, and four network series with Python EDA; CSV and Matplotlib PNG exports pass. Invalid requests return HTTP 400.
- Browser verification passed for desktop rendering, outlier filtering (14 matches), BTC network statistics/correlations, Ethereum switching, and a 390px mobile layout without horizontal overflow. No browser errors. Scanned 20 browser build assets: no API key found. Inspected and corrected PNG footer spacing.
- Deployment is configured but not published. The local production integration is verified; Vercel's hosted Python packaging/routing must still be checked on the first GitHub deployment. No external source upload or GitHub push was performed.
