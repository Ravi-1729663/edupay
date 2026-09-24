import type { NextRequest } from "next/server";

/**
 * Server-side proxy: frontend → /api/edupay/<path> → backend.
 *
 * The Next.js server (port 3000) runs in the sandbox host and CAN reach the
 * backend on localhost:8000 directly (no browser CORS/preview-proxy in the
 * way). This keeps the frontend's API calls same-origin (no CORS preflight)
 * and works identically in docker (set BACKEND_URL=http://backend:8000).
 *
 * The catch-all `[...path]` captures everything after /api/edupay/, so
 * `fetch('/api/edupay/auth/login')` → `${BACKEND_URL}/auth/login`.
 */

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length", // re-computed by fetch
]);

async function proxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const pathStr = path.map(encodeURIComponent).join("/");
  // Preserve the query string (which may include XTransformPort from older
  // callers, but we strip it since we talk to the backend directly).
  const url = new URL(req.url);
  const backendUrl = `${BACKEND_URL}/${pathStr}${url.search ? url.search : ""}`;

  // Forward headers except hop-by-hop ones.
  const headers: Record<string, string> = {};
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers[key] = value;
    }
  });

  // Read body for methods that have one.
  let body: BodyInit | undefined = undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await req.arrayBuffer();
  }

  const resp = await fetch(backendUrl, {
    method: req.method,
    headers,
    body,
    // Never cache API responses.
    cache: "no-store",
  });

  // Forward response headers (minus hop-by-hop).
  const respHeaders = new Headers();
  resp.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      respHeaders.set(key, value);
    }
  });

  return new Response(resp.body, {
    status: resp.status,
    statusText: resp.statusText,
    headers: respHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;

export const dynamic = "force-dynamic";
