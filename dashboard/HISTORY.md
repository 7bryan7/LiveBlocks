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
