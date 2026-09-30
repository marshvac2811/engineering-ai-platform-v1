import { next } from "@vercel/functions";

const SUPABASE_URL = "https://vaxerlbgwwlfamncevdg.supabase.co";
const ISSUER = SUPABASE_URL + "/auth/v1";
const JWKS_URL = ISSUER + "/.well-known/jwks.json";
const JWKS_TTL_MS = 10 * 60 * 1000;

let jwksCache = null;
let jwksFetchedAt = 0;
const membershipCache = new Map();

function base64UrlToBytes(value) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (value.length % 4)) % 4);
  const binary = atob(normalized);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function decodeJsonPart(value) {
  const bytes = base64UrlToBytes(value);
  return JSON.parse(new TextDecoder().decode(bytes));
}

function base64UrlJson(value) {
  const binary = btoa(JSON.stringify(value));
  return binary.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

async function fetchJwks(force = false) {
  const now = Date.now();
  if (!force && jwksCache && now - jwksFetchedAt < JWKS_TTL_MS) return jwksCache;

  const response = await fetch(JWKS_URL, {
    headers: { accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Supabase JWKS returned HTTP " + response.status);

  const payload = await response.json();
  if (!payload || !Array.isArray(payload.keys)) throw new Error("Supabase JWKS payload is invalid");

  jwksCache = payload;
  jwksFetchedAt = now;
  return payload;
}

async function verifySupabaseJwt(token) {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("Supabase access token is not a JWT");

  const header = decodeJsonPart(parts[0]);
  const claims = decodeJsonPart(parts[1]);
  const algorithm = String(header.alg || "");
  const kid = String(header.kid || "");

  if (!kid || !["ES256", "RS256"].includes(algorithm)) {
    throw new Error("Unsupported Supabase JWT signing algorithm");
  }

  const verifyWith = async (jwks) => {
    const jwk = jwks.keys.find((key) => String(key.kid || "") === kid && String(key.alg || algorithm) === algorithm);
    if (!jwk) return false;

    const keyAlgorithm =
      algorithm === "ES256"
        ? { name: "ECDSA", namedCurve: "P-256" }
        : { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" };

    const verifyAlgorithm =
      algorithm === "ES256"
        ? { name: "ECDSA", hash: "SHA-256" }
        : { name: "RSASSA-PKCS1-v1_5" };

    const key = await crypto.subtle.importKey("jwk", jwk, keyAlgorithm, false, ["verify"]);
    return crypto.subtle.verify(
      verifyAlgorithm,
      key,
      base64UrlToBytes(parts[2]),
      new TextEncoder().encode(parts[0] + "." + parts[1]),
    );
  };

  let verified = await verifyWith(await fetchJwks(false));
  if (!verified) verified = await verifyWith(await fetchJwks(true));
  if (!verified) throw new Error("Supabase JWT signature verification failed");

  if (claims.iss !== ISSUER) throw new Error("Supabase JWT issuer is invalid");
  const audience = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (!audience.includes("authenticated")) throw new Error("Supabase JWT audience is invalid");
  if (!claims.sub) throw new Error("Supabase JWT subject is missing");
  if (!Number.isFinite(Number(claims.exp)) || Number(claims.exp) <= Math.floor(Date.now() / 1000)) {
    throw new Error("Supabase JWT is expired");
  }

  return claims;
}

async function resolveTenant(userId, claims) {
  const metadata = claims.app_metadata;
  const metadataTenant = metadata && String(metadata.tenant_id || "").trim();
  const metadataRole = metadata && String(metadata.app_role || "").trim();
  if (metadataTenant) {
    return {
      tenant_id: metadataTenant,
      role: metadataRole || "member",
    };
  }

  const cached = membershipCache.get(userId);
  if (cached && cached.expiresAt > Date.now()) return cached.value;

  const serviceKey = String(process.env.SUPABASE_SERVICE_ROLE_KEY || "").trim();
  if (!serviceKey) throw new Error("Tenant membership is unavailable");

  const url =
    SUPABASE_URL +
    "/rest/v1/tenant_memberships?user_id=eq." +
    encodeURIComponent(userId) +
    "&select=tenant_id,role,is_default&order=is_default.desc&limit=1";

  const response = await fetch(url, {
    headers: {
      apikey: serviceKey,
      Authorization: "Bearer " + serviceKey,
      accept: "application/json",
    },
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Tenant membership lookup returned HTTP " + response.status);

  const rows = await response.json();
  if (!Array.isArray(rows) || !rows.length || !rows[0].tenant_id) {
    throw new Error("Authenticated user has no active tenant membership");
  }

  const value = {
    tenant_id: String(rows[0].tenant_id),
    role: String(rows[0].role || "member"),
  };
  membershipCache.set(userId, { value, expiresAt: Date.now() + 5 * 60 * 1000 });
  return value;
}

export const config = {
  matcher: ["/v1/:path*", "/api/:path*"],
};

export default async function middleware(request) {
  const headers = new Headers(request.headers);

  // Never accept this internal context from the browser.
  headers.delete("x-engineering-auth");

  const authorization = headers.get("authorization") || "";
  if (!authorization.startsWith("Bearer ")) {
    return new Response(JSON.stringify({ error: "Authentication required" }), {
      status: 401,
      headers: { "content-type": "application/json" },
    });
  }

  try {
    const token = authorization.slice(7).trim();
    const claims = await verifySupabaseJwt(token);
    const membership = await resolveTenant(String(claims.sub), claims);

    const context = {
      sub: String(claims.sub),
      tenant_id: membership.tenant_id,
      role: membership.role,
      scopes: Array.isArray(claims.scopes) ? claims.scopes : [],
      exp: Number(claims.exp),
    };

    headers.set("x-engineering-auth", base64UrlJson(context));
    return next({ request: { headers } });
  } catch (error) {
    return new Response(JSON.stringify({
      error: "Invalid Supabase JWT: " + String(error && error.message ? error.message : error),
    }), {
      status: 401,
      headers: { "content-type": "application/json" },
    });
  }
}
