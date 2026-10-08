// Presentation metadata and immediate form validation only. All data preparation/EDA is Python.
export const METRICS = [
  { id: 'market-price', name: 'Bitcoin price', short: 'Price', unit: 'USD', color: '#4acda5' },
  { id: 'n-transactions', name: 'Daily transactions', short: 'Transactions', unit: 'transactions', color: '#7798ff' },
  { id: 'hash-rate', name: 'Network hash rate', short: 'Hash rate', unit: 'TH/s', color: '#b199f4' },
  { id: 'transaction-fees-usd', name: 'Network fees', short: 'Fees', unit: 'USD', color: '#e2b26a' },
];
export const DEFAULT_ADDRESS='bc1qq8dxdalmj3f89v5xm5f3y70sec9s0fa7qpesl7';
export function validAddress(address){return typeof address==='string'&&/^(bc1[a-z0-9]{20,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$/.test(address);}
export const DEFAULT_ETH_ADDRESS='0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe';
export function validEthAddress(address){return typeof address==='string'&&/^0x[0-9a-fA-F]{40}$/.test(address);}
