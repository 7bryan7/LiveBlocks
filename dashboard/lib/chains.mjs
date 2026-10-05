export const DEFAULT_ETH_ADDRESS='0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe';
export function validEthAddress(address){return typeof address==='string'&&/^0x[0-9a-fA-F]{40}$/.test(address);}
