import { NextRequest } from 'next/server';
import { isSameOrigin } from '../../../lib/request-origin';

export const runtime = 'nodejs';
export const maxDuration = 300;
// The application token stays on the Next.js server. Local services bind to
// loopback. Add end-user authentication before exposing this server publicly.
async function proxy(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  const {path} = await context.params;
  const route = path.join('/');
  if (!/^(ask|freshness|transcribe|reports|reports\/[A-Za-z0-9_-]+\/embed)$/.test(route)) return Response.json({detail:'Not found'}, {status:404});
  const origin = request.headers.get('origin');
  if (request.method === 'POST' && origin && !isSameOrigin(origin, request.headers.get('host'), request.url, process.env.VERCEL === '1' ? 'https:' : undefined)) return Response.json({detail:'Request origin is not allowed. Open this app directly at its local URL.'}, {status:403});
  try {
    const headers: Record<string,string> = { Authorization: `Bearer ${process.env.APP_API_TOKEN || ''}` };
    const contentType = request.headers.get('content-type');
    if(contentType) headers['content-type'] = contentType;
    const body = request.method === 'POST' ? await request.arrayBuffer() : undefined;
    if(body && body.byteLength > 21 * 1024 * 1024) return Response.json({detail:'Request too large'}, {status:413});
    const response = await fetch(`${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/api/${route}`, {method:request.method, headers, body, cache:'no-store', signal:AbortSignal.timeout(180000)});
    return new Response(await response.arrayBuffer(), {status:response.status, headers:{'content-type':response.headers.get('content-type') || 'application/json','cache-control':'no-store'}});
  } catch { return Response.json({detail:'Backend unavailable. Start the API and check its configuration.'}, {status:503}); }
}
export { proxy as GET, proxy as POST };
