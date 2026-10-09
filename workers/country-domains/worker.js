// Nordic Crypto country domains (Cloudflare Worker "nordiccrypto-country-domains").
//
// nordiccrypto.se / .fi / .dk / .is (apex) serve the site from https://nordiccrypto.no (GitHub Pages) under their
// own address. www.<country> answers 301 to the apex on the same country domain. Nothing is stored or logged.
//
//   /                -> origin /<lang>/   (the country's language home; Swedish on .se, Finnish on .fi, ...)
//   /<lang>/         -> 301 to /          (the country's own language lives at the root)
//   /en/             -> origin /          (English home; the IP language auto-select script is removed there)
//   anything else    -> the same path on the origin (/about/, /da/stories/..., /assets/..., /api/v1/..., ...)
//
// In HTML, links that point at nordiccrypto.no (absolute or relative) are rewritten to paths on the country domain
// with the mapping above, so navigation stays on e.g. nordiccrypto.se. <link rel=canonical>, the hreflang
// alternates, og:url and share links keep pointing to https://nordiccrypto.no (one canonical site for search engines).
// Redirect Location headers from the origin are mapped the same way.
// An explicit language choice (the nc_lang cookie set by the site's language switcher) wins on "/".

const ORIGIN = "https://nordiccrypto.no";
const ORIGIN_HOSTS = new Set(["nordiccrypto.no", "www.nordiccrypto.no"]);
const COUNTRY = {
  "nordiccrypto.se": "sv",
  "nordiccrypto.fi": "fi",
  "nordiccrypto.dk": "da",
  "nordiccrypto.is": "is",
};
// Site languages (i18n.LANGS). English is the origin root; "en" is only a path on the country domains.
const LANGS = ["en", "nn", "nb", "sv", "da", "fi", "is", "zh", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur",
  "id", "de", "ja", "sw", "mr", "fa"];

// Origin path -> path on the country domain.
export function toCountryPath(path, lang) {
  if (path === "/" || path === "/index.html") return "/en/";
  if (path === `/${lang}/` || path === `/${lang}/index.html`) return "/";
  return path;
}

// Country-domain path -> what to do: {origin: path} to proxy, or {redirect: path} to redirect.
export function route(path, lang, cookie) {
  if (path === "/" || path === "/index.html") {
    const m = String(cookie || "").match(/(?:^|;\s*)nc_lang=([a-z]{2})(?:;|$)/);
    const pick = m && LANGS.includes(m[1]) ? m[1] : null;
    if (pick && pick !== lang) return { redirect: pick === "en" ? "/en/" : `/${pick}/`, status: 302 };
    return { origin: `/${lang}/` };
  }
  if (path === `/${lang}/` || path === `/${lang}/index.html`) return { redirect: "/", status: 301 };
  if (path === "/en" ) return { redirect: "/en/", status: 301 };
  if (path === "/en/" || path === "/en/index.html") return { origin: "/", english: true };
  if (path.startsWith("/en/")) return { redirect: toCountryPath(path.slice(3), lang), status: 302 };
  return { origin: path };
}

// Rewrites one URL attribute value found in a page whose origin URL is pageUrl. Returns null to leave it alone.
export function mapUrl(value, pageUrl, lang) {
  const v = (value || "").trim();
  if (!v || v.startsWith("#") || /^(data|mailto|tel|javascript|blob):/i.test(v)) return null;
  let u;
  try { u = new URL(v, pageUrl); } catch (e) { return null; }
  if (u.protocol !== "https:" && u.protocol !== "http:") return null;
  if (!ORIGIN_HOSTS.has(u.hostname)) return null;
  return toCountryPath(u.pathname, lang) + u.search + u.hash;
}

const LANGSELECT = /<script>(?:(?!<\/script>)[\s\S])*?(?:ncLang|BY_COUNTRY)(?:(?!<\/script>)[\s\S])*?<\/script>/g;

function rewriter(pageUrl, lang) {
  const attr = (name) => ({
    element(el) {
      const v = el.getAttribute(name);
      const m = mapUrl(v, pageUrl, lang);
      if (m !== null && m !== v) el.setAttribute(name, m);
    },
  });
  const srcset = {
    element(el) {
      const v = el.getAttribute("srcset");
      if (!v) return;
      el.setAttribute("srcset", v.split(",").map((part) => {
        const p = part.trim().split(/\s+/);
        const m = mapUrl(p[0], pageUrl, lang);
        if (m !== null) p[0] = m;
        return p.join(" ");
      }).join(", "));
    },
  };
  return new HTMLRewriter()
    .on("a[href]", attr("href"))
    .on("area[href]", attr("href"))
    .on("form[action]", attr("action"))
    .on("select.langsel option[value]", attr("value"))
    .on("img[src]", attr("src"))
    .on("script[src]", attr("src"))
    .on("iframe[src]", attr("src"))
    .on("source[src]", attr("src"))
    .on("video[src]", attr("src"))
    .on("video[poster]", attr("poster"))
    .on("audio[src]", attr("src"))
    .on("img[srcset]", srcset)
    .on("source[srcset]", srcset)
    // stylesheets, icons, preloads and feeds; canonical and alternate links stay on nordiccrypto.no
    .on("link[href]", {
      element(el) {
        const rel = ` ${(el.getAttribute("rel") || "").toLowerCase()} `;
        if (/ (canonical|alternate) /.test(rel)) return;
        const v = el.getAttribute("href");
        const m = mapUrl(v, pageUrl, lang);
        if (m !== null && m !== v) el.setAttribute("href", m);
      },
    });
}

async function handle(req) {
  const url = new URL(req.url);
  const host = url.hostname.toLowerCase();
  if (host.startsWith("www.") && COUNTRY[host.slice(4)]) {
    return Response.redirect(`https://${host.slice(4)}${url.pathname}${url.search}`, 301);
  }
  const lang = COUNTRY[host];
  if (!lang) return new Response("Not found", { status: 404 });
  if (url.protocol === "http:") return Response.redirect(`https://${host}${url.pathname}${url.search}`, 301);

  const r = route(url.pathname, lang, req.headers.get("Cookie"));
  if (r.redirect) {
    return new Response(null, { status: r.status, headers: { Location: `https://${host}${r.redirect}${url.search}`, "Cache-Control": r.status === 302 ? "no-store" : "public, max-age=3600" } });
  }

  const target = new URL(r.origin + url.search, ORIGIN);
  const headers = new Headers(req.headers);
  for (const k of [...headers.keys()]) if (k.startsWith("cf-") || k === "x-forwarded-proto" || k === "x-real-ip") headers.delete(k);
  headers.delete("host");
  headers.delete("cookie");          // GitHub Pages uses no cookies; the site's cookies stay on the country domain
  const res = await fetch(target.toString(), {
    method: req.method,
    headers,
    body: req.method === "GET" || req.method === "HEAD" ? undefined : req.body,
    redirect: "manual",
  });

  const out = new Headers(res.headers);
  const loc = out.get("Location");
  if (loc) {
    const m = mapUrl(loc, target.toString(), lang);
    if (m !== null) out.set("Location", `https://${host}${m}`);
  }
  out.set("X-Served-By", "nordiccrypto-country-domains");
  if (r.origin === `/${lang}/`) out.set("Cache-Control", "no-cache");   // "/" depends on the nc_lang cookie

  const type = (out.get("Content-Type") || "").toLowerCase();
  if (!type.includes("text/html") || req.method === "HEAD" || res.status === 304 || !res.body) {
    return new Response(res.body, { status: res.status, statusText: res.statusText, headers: out });
  }
  out.delete("Content-Length");
  out.delete("ETag");                 // the body is changed below
  let body = res.body;
  if (r.english) {
    // The English home inlines the IP-based language auto-select (tools/langselect.js). On a country domain the
    // country language is the default, so that script is removed from /en/.
    body = (await res.text()).replace(LANGSELECT, "");
  }
  const plain = new Response(body, { status: res.status, statusText: res.statusText, headers: out });
  return rewriter(target.toString(), lang).transform(plain);
}

export default {
  async fetch(req) {
    try {
      return await handle(req);
    } catch (e) {
      return new Response("Temporarily unavailable. The site is at https://nordiccrypto.no/", { status: 502, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
    }
  },
};
