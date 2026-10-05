import { existsSync, writeFileSync, chmodSync } from 'node:fs';
import { loadEnvFile } from 'node:process';
if (existsSync('.env')) loadEnvFile('.env');
const allowed = ['BLOCKCHAIN_API_KEY', 'BLOCKCHAIN_API_BASE_URL'];
const text = allowed.filter(k => process.env[k]).map(k => `${k}=${JSON.stringify(process.env[k])}`).join('\n');
writeFileSync('dashboard/.dev.vars', text + '\n', { mode: 0o600 });
chmodSync('dashboard/.dev.vars', 0o600);
console.log(`Gateway configuration ready. API key: ${process.env.BLOCKCHAIN_API_KEY ? 'configured' : 'not configured; public access'}.`);
