import { fresh, todayIn, buildPlan } from "../web/model.js";
import { apply, InputError, zoneName } from "./actions.js";

const enc = new TextEncoder();
function json(data, status = 200) {
  return Response.json(data, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
function hex(buf) {
  return Array.from(new Uint8Array(buf), (b) =>
    b.toString(16).padStart(2, "0"),
  ).join("");
}
async function sessionKey(password) {
  return crypto.subtle.importKey(
    "raw",
    enc.encode(password),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}
async function issue(password, browserSession = false) {
  const payload =
    (browserSession ? "session" : String(Date.now() + 12 * 3600000)) +
    "." +
    crypto.randomUUID();
  const sig = await crypto.subtle.sign(
    "HMAC",
    await sessionKey(password),
    enc.encode(payload),
  );
  return payload + "." + hex(sig);
}
async function authorized(request, password) {
  const cookie = request.headers
    .get("Cookie")
    ?.split(";")
    .map((v) => v.trim())
    .find((v) => v.startsWith("p514_session="))
    ?.slice(13);
  const token = cookie
    ? "Bearer " + cookie
    : request.headers.get("Authorization") || "";
  const match =
    /^Bearer ((?:session|\d{13})\.[a-f0-9-]{36})\.([a-f0-9]{64})$/.exec(token);
  if (
    !match ||
    (match[1].split(".")[0] !== "session" &&
      Number(match[1].split(".")[0]) < Date.now())
  )
    return false;
  return crypto.subtle.verify(
    "HMAC",
    await sessionKey(password),
    Uint8Array.from(match[2].match(/../g), (b) => parseInt(b, 16)),
    enc.encode(match[1]),
  );
}
async function login(db, password, supplied, ip, secure) {
  const hash = new Uint8Array(
    await crypto.subtle.digest("SHA-256", enc.encode(ip)),
  );
  const slot = (hash[0] << 8) + hash[1],
    now = Date.now();
  // Reserve an attempt atomically, including concurrent requests.
  const row = await db
    .prepare(
      "INSERT INTO login_attempt VALUES(?,1,?) ON CONFLICT(slot) DO UPDATE SET failures=CASE WHEN expires<=? THEN 1 ELSE failures+1 END,expires=CASE WHEN expires<=? THEN excluded.expires ELSE expires END WHERE failures<10 OR expires<=? RETURNING failures",
    )
    .bind(slot, now + 300000, now, now, now)
    .first();
  if (!row)
    return json(
      { error: "Too many attempts. Try again in five minutes." },
      429,
    );
  const expected = await crypto.subtle.digest("SHA-256", enc.encode(password));
  const actual = await crypto.subtle.digest(
    "SHA-256",
    enc.encode(typeof supplied === "string" ? supplied : ""),
  );
  if (!crypto.subtle.timingSafeEqual(expected, actual))
    return json({ error: "That password didn’t match." }, 401);
  await db.prepare("DELETE FROM login_attempt WHERE slot=?").bind(slot).run();
  const response = json({ token: await issue(password) });
  response.headers.set(
    "Set-Cookie",
    sessionCookie(await issue(password, true), secure),
  );
  return response;
}
function sessionCookie(value, secure, clear = false) {
  return (
    "p514_session=" +
    value +
    "; Path=/api; HttpOnly; SameSite=Strict" +
    (secure ? "; Secure" : "") +
    (clear ? "; Max-Age=0" : "")
  );
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    try {
      if (!env.APP_PASSWORD || env.APP_PASSWORD.length < 16 || !env.DB)
        return json(
          {
            error:
              "Configure D1 and an APP_PASSWORD of at least 16 characters.",
          },
          503,
        );
      const post = request.method === "POST";
      if (
        post &&
        request.headers.get("Origin") &&
        request.headers.get("Origin") !== url.origin
      )
        return json({ error: "Invalid origin." }, 403);
      if (
        post &&
        !request.headers.get("Content-Type")?.startsWith("application/json")
      )
        return json({ error: "JSON required." }, 415);
      if (url.pathname === "/api/logout" && post) {
        const response = json({ ok: true });
        response.headers.set(
          "Set-Cookie",
          sessionCookie("", url.protocol === "https:", true),
        );
        return response;
      }
      if (url.pathname === "/api/login" && post) {
        const body = await request.json();
        return login(
          env.DB,
          env.APP_PASSWORD,
          body.password,
          request.headers.get("CF-Connecting-IP") || "local",
          url.protocol === "https:",
        );
      }
      if (!(await authorized(request, env.APP_PASSWORD)))
        return json({ error: "Enter your app password." }, 401);
      if (url.pathname !== "/api/state" || (!post && request.method !== "GET"))
        return json({ error: "Unknown endpoint." }, 404);
      const browserZone = zoneName(
        request.headers.get("X-Time-Zone") || request.cf?.timezone || "UTC",
      );
      const row = await env.DB.prepare(
        "SELECT revision,payload FROM athlete WHERE id=1",
      ).first();
      const s = row ? JSON.parse(row.payload) : fresh();
      if (s.profile && (s.plannerVersion || 0) < 6)
        buildPlan(
          s,
          todayIn(s.profile.zone === "auto" ? browserZone : s.profile.zone),
        );
      let rev = row?.revision || 0;
      if (post) {
        const body = await request.json();
        const conflict = () =>
          json(
            {
              error:
                "Another tab updated your log. Reload the latest plan before saving.",
            },
            409,
          );
        if (body.revision !== rev) return conflict();
        apply(s, body, browserZone);
        const result = row
          ? await env.DB.prepare(
              "UPDATE athlete SET payload=?,revision=revision+1 WHERE id=1 AND revision=?",
            )
              .bind(JSON.stringify(s), rev)
              .run()
          : await env.DB.prepare("INSERT OR IGNORE INTO athlete VALUES(1,1,?)")
              .bind(JSON.stringify(s))
              .run();
        if (!result.meta.changes) return conflict();
        rev++;
      }
      return json({
        state: s,
        revision: rev,
        today: todayIn(
          s.profile?.zone && s.profile.zone !== "auto"
            ? s.profile.zone
            : browserZone,
        ),
      });
    } catch (e) {
      if (e instanceof InputError || e instanceof SyntaxError)
        return json({ error: e.message }, 400);
      console.error("Training log request failed", e.name);
      return json(
        {
          error:
            "Couldn’t open or save the log. Check the D1 binding and migrations, then retry.",
        },
        503,
      );
    }
  },
};
