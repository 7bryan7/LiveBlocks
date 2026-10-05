import { fetchSnapshot, RANGES } from '@/lib/gateway.mjs';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 30;

type Snapshot = Awaited<ReturnType<typeof fetchSnapshot>>;
const cache = new Map<string, { at: number; data: Snapshot }>();
const pending = new Map<string, Promise<Snapshot>>();
export async function GET(request: Request) {
  const days = Number(new URL(request.url).searchParams.get('days') || 30);
  if (!RANGES.includes(days)) return Response.json({ error: 'Choose 7, 30, 90, or 365 days.' }, { status: 400 });
  // Charts are public network context. The configured Explorer key is scoped to
  // address endpoints and was rejected by chart routes during verification.
  // Do not retry failed authenticated requests with silently reduced auth.
  const config = {base: process.env.BLOCKCHAIN_API_BASE_URL, key: undefined};
  const cacheKey = JSON.stringify([days, config.base, config.key]);
  const saved = cache.get(cacheKey);
  if (saved && Date.now()-saved.at < 60000) return Response.json(saved.data, {headers:{'Cache-Control':'no-store'}});
  try {
    let work = pending.get(cacheKey);
    if (!work) {
      work = fetchSnapshot(days, config).then(data => {
        if (cache.size >= 8) cache.clear();
        cache.set(cacheKey,{at:Date.now(),data});
        return data;
      }).finally(()=>pending.delete(cacheKey));
      pending.set(cacheKey,work);
    }
    return Response.json(await work, {headers:{'Cache-Control':'no-store'}});
  } catch {
    return Response.json({error:'Unable to load the configured gateway. Check server configuration.'},{status:502});
  }
}
