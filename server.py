#!/usr/bin/env python3
"""Public server for the Bismarck deck, plus the phone follow-along.

Public routes
  /                 the live deck, backstage demo-links slide removed
  /img/*  /fonts/*  static assets
  /follow           mobile follow-along page (chapters, Q1 to Q20, use cases)
  /api/content      chapters, requirements and use cases, parsed from the LIVE deck file
  /api/state        GET: current ticks (poll)          /api/stream: same, as SSE
  /follow-qr.svg    QR code for the public /follow URL   /follow-qr.png
Presenter only (key in presenter.key, sent as X-Presenter-Key header or the cookie
set by opening /?presenter=<key>)
  /?presenter=<key> the full deck with the sync script injected
  POST /api/state   write ticks          POST /api/reset   clear all ticks
Everything else is 404."""
import http.server, os, mimetypes, json, re, threading, time, hmac, hashlib, io, secrets
import urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLE = os.path.join(HERE, "deck")                 # copy shipped for cloud hosting (see publish.sh)
_SRC = os.path.expanduser("~/Bismarck-RFP-Deck")
_DECK_DIR = _SRC if os.path.isdir(_SRC) else _BUNDLE
DECK = os.path.join(_DECK_DIR, "Bismarck-Presentation.html")
IMG = os.path.join(_DECK_DIR, "img")
FONTS = os.path.join(HERE, "fonts")
KEY_FILE = os.path.join(HERE, "presenter.key")
DATA_DIR = os.environ.get("DATA_DIR") or HERE          # Render: a persistent disk, see render.yaml
os.makedirs(DATA_DIR, exist_ok=True)
STATE_FILE = os.path.join(DATA_DIR, "state.json")
LEADS_FILE = os.path.join(DATA_DIR, "leads.jsonl")
CONTENT_FILE = os.path.join(HERE, "content.last-good.json")
URL_FILE = os.path.join(HERE, "url.txt")
QA_URL_FILE = os.path.join(HERE, "qa-url.txt")      # optional override for the Q&A portal link
ANCHOR = "SCENES.forEach((sc,i)=>{ if(!__SRC[i] && __SRCMAP[sc.t])"
STRIP = '(function(){const k=SCENES.filter(s=>s.t!=="backstage");SCENES.length=0;k.forEach(s=>SCENES.push(s));})();\n'
COOKIE = "bis_presenter"

# ---------------------------------------------------------------- presenter key
if os.environ.get("PRESENTER_KEY"): KEY = os.environ["PRESENTER_KEY"].strip()
elif not os.path.exists(KEY_FILE):
    with open(KEY_FILE, "w") as f: f.write(secrets.token_urlsafe(24) + "\n")
    os.chmod(KEY_FILE, 0o600)
if not os.environ.get("PRESENTER_KEY"): KEY = open(KEY_FILE).read().strip()
def key_ok(k): return bool(k) and hmac.compare_digest(str(k).encode(), KEY.encode())

# ---------------------------------------------------------------- access code (login screen)
# Everyone needs the code to see anything. The QR carries it (?code=...), so phones skip the
# screen; people given the bare link type it once. Set ACCESS_CODE to choose your own; otherwise
# it is derived from the presenter key, so it stays the same across restarts and deploys.
_ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
def _derive_code():
    d = hmac.new(KEY.encode(), b"bismarck-access", hashlib.sha256).digest()
    return "".join(_ALPHA[b % len(_ALPHA)] for b in d[:6])
CODE = (os.environ.get("ACCESS_CODE") or "").strip().upper() or _derive_code()
ACOOKIE = "bis_access"
ATOKEN = hmac.new(KEY.encode(), ("access:" + CODE).encode(), hashlib.sha256).hexdigest()[:32]
def code_ok(c): return bool(c) and hmac.compare_digest(re.sub(r"[\s-]", "", str(c)).upper().encode(), CODE.encode())
OPEN_IMG = {"accela-logo.png", "novotx-logo.png", "bismarck-logo.png", "bismarck-logo-white.png", "novotx-logo-white.png"}
_FAILS = {}
def too_many(ip):
    now = time.time(); f = [t for t in _FAILS.get(ip, []) if now - t < 600]; _FAILS[ip] = f
    return len(f) >= 10
LOGIN_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>City of Bismarck presentation</title>
<style>
@font-face{font-family:PJS;src:url(/fonts/pjs-400.woff2) format("woff2");font-weight:400}
@font-face{font-family:PJS;src:url(/fonts/pjs-600.woff2) format("woff2");font-weight:600}
*{box-sizing:border-box}html,body{overflow-x:hidden}body{margin:0;min-height:100vh;display:grid;grid-template-columns:minmax(0,420px);justify-content:center;align-content:center;font-family:PJS,system-ui,sans-serif;
background:radial-gradient(900px 560px at 84% -14%,rgba(0,175,241,.22),transparent 62%),#0D263A;color:#fff;padding:24px}
.card{width:100%;max-width:420px}
.logos{display:flex;align-items:center;gap:14px;margin-bottom:44px;flex-wrap:wrap}.logos img{height:20px;width:auto;max-width:34%;object-fit:contain;display:block}
.logos img.city{height:28px}.logos i{width:1px;height:20px;background:rgba(255,255,255,.25)}
h1{font-size:34px;font-weight:600;letter-spacing:-.02em;margin:0 0 10px}
p{font-size:17px;color:#B9CBD6;margin:0 0 30px;line-height:1.45}
input{width:100%;font:600 26px PJS,system-ui;letter-spacing:.28em;text-transform:uppercase;text-align:center;padding:18px;
border-radius:14px;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.06);color:#fff;outline:none}
input:focus{border-color:#00AFF1;background:rgba(255,255,255,.1)}
button{margin-top:14px;width:100%;font:600 18px PJS,system-ui;padding:18px;border:0;border-radius:14px;background:#0068BE;color:#fff;cursor:pointer}
button:hover{background:#0B77CF}.err{color:#FFB38A;font-size:16px;margin:14px 0 0;min-height:1em}
</style></head><body><form class="card" method="post" action="/login">
<div class="logos"><img src="/img/accela-logo.png" alt="Accela" style="filter:brightness(0) invert(1)"><i></i>
<img src="/img/novotx-logo-white.png" alt="Novotx"><i></i><img class="city" src="/img/bismarck-logo-white.png" alt="City of Bismarck"></div>
<h1>Welcome</h1><p>Enter the access code you were given to view the presentation.</p>
<input name="code" autocomplete="off" autocapitalize="characters" spellcheck="false" inputmode="text" maxlength="12" autofocus aria-label="Access code">
<input type="hidden" name="next" value="__NEXT__">
<button type="submit">Continue</button><div class="err">__ERR__</div></form></body></html>"""

# ---------------------------------------------------------------- JS literal -> JSON
class ParseError(Exception): pass

def _js_string(s, i):
    q = s[i]; i += 1; out = []
    while i < len(s):
        c = s[i]
        if c == "\\":
            n = s[i + 1]
            if n == "u": out.append(chr(int(s[i + 2:i + 6], 16))); i += 6; continue
            if n == "x": out.append(chr(int(s[i + 2:i + 4], 16))); i += 4; continue
            out.append({"n": "\n", "t": "\t", "r": "", "b": "", "f": "", "0": "", "\n": ""}.get(n, n)); i += 2; continue
        if c == q: return "".join(out), i + 1
        if c == "\n": raise ParseError("newline in string")
        out.append(c); i += 1
    raise ParseError("unterminated string")

def js_to_py(src):
    toks, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c.isspace(): i += 1; continue
        if src.startswith("//", i): i = src.find("\n", i); i = n if i < 0 else i; continue
        if src.startswith("/*", i): i = src.find("*/", i) + 2; continue
        if c in "\"'": v, i = _js_string(src, i); toks.append(json.dumps(v)); continue
        if c == "`": raise ParseError("template literal")
        if c in "{}[]:,":
            if c in "}]" and toks and toks[-1] == ",": toks.pop()
            toks.append(c); i += 1; continue
        m = re.match(r"-?\d+(\.\d+)?", src[i:])
        if m: toks.append(m.group(0)); i += len(m.group(0)); continue
        m = re.match(r"[A-Za-z_$][\w$]*", src[i:])
        if m:
            w = m.group(0); i += len(w)
            if w in ("true", "false", "null"): toks.append(w)
            else:
                j = i
                while j < n and src[j].isspace(): j += 1
                if j < n and src[j] == ":": toks.append(json.dumps(w))
                else: raise ParseError("expression: " + w)
            continue
        raise ParseError("unexpected %r" % c)
    return json.loads("".join(toks))

def _literal_after(html, name):
    """Source text of the last `CITY.<name> = <literal>` in the file."""
    ms = list(re.finditer(r"CITY\." + re.escape(name) + r"\s*=\s*(?=[\[{])", html))
    if not ms: raise ParseError("CITY.%s not found" % name)
    i = ms[-1].end(); depth = 0; j = i
    while j < len(html):
        c = html[j]
        if c in "\"'": _, j = _js_string(html, j); continue
        if c in "[{": depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0: return html[i:j + 1]
        j += 1
    raise ParseError("unbalanced CITY.%s" % name)

def _img(p):
    name = os.path.basename(p or "")
    return "/img/" + name if name and os.path.isfile(os.path.join(IMG, name)) else ""

def extract(html):
    chapters = js_to_py(_literal_after(html, "chapters"))
    for m in re.finditer(r'CITY\.chapters\[(\d+)\]\.(\w+)\s*=\s*(?=["\'])', html):
        k = int(m.group(1))
        if k < len(chapters): chapters[k][m.group(2)] = _js_string(html, m.end())[0]
    try: outcomes = js_to_py(_literal_after(html, "outcomes"))
    except ParseError: outcomes = {}
    try: proof = js_to_py(_literal_after(html, "proof6"))
    except ParseError: proof = []
    out = []
    for i, c in enumerate(chapters):
        p = proof[i] if i < len(proof) and isinstance(proof[i], dict) else {}
        use = None
        if p.get("who"):
            stat = p.get("stat") or ["", ""]
            use = {"label": p.get("label", ""), "who": p["who"], "st": p.get("st", ""), "tag": p.get("tag", ""),
                   "logo": _img(p.get("logo")), "problem": p.get("problem", ""), "stat": stat[0] if stat else "",
                   "statLabel": stat[1] if len(stat) > 1 else "", "quote": p.get("quote", ""), "by": p.get("qby", ""),
                   "here": p.get("here", "")}
        elif p.get("honest"):
            use = {"honest": True, "h": p["honest"].get("h", ""), "d": p["honest"].get("d", ""), "here": p.get("here", "")}
        reqs = [{"id": r[0], "text": r[1], "hi": bool(len(r) > 2 and r[2]), "outcome": outcomes.get(r[0], "")}
                for r in c.get("reqs", []) if isinstance(r, list) and len(r) >= 2]
        out.append({"n": c.get("n", "%02d" % (i + 1)), "title": c.get("t", ""), "q": c.get("q", ""), "mins": c.get("mins", ""),
                    "line": c.get("line", ""), "impact": c.get("impact", ""), "url": c.get("url", ""),
                    "hi": bool(c.get("hi")), "reqs": reqs, "use": use})
    if not out or not sum(len(c["reqs"]) for c in out): raise ParseError("no requirements found")
    return {"chapters": out, "total": sum(len(c["reqs"]) for c in out)}

# ---------------------------------------------------------------- link checks (only verified links reach phones)
LINKS = {}      # url -> (ok, checked_at)
def check_link(u):
    try:
        r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36"})
        with urllib.request.urlopen(r, timeout=12) as resp: ok = resp.status == 200
    except Exception: ok = False
    LINKS[u] = (ok, time.time())
def link_ok(u):
    if not re.match(r"https://", u or ""): return False
    v = LINKS.get(u)
    if v is None or time.time() - v[1] > 1800:
        threading.Thread(target=check_link, args=(u,), daemon=True).start()
    return bool(v and v[0])

_CACHE = {"mtime": None, "data": None, "error": None}
_CLOCK = threading.Lock()
def content():
    with _CLOCK:
        try: mt = os.path.getmtime(DECK)
        except OSError: mt = None
        if mt != _CACHE["mtime"] or _CACHE["data"] is None:
            _CACHE["mtime"] = mt
            try:
                d = extract(open(DECK, encoding="utf-8").read())
                with open(CONTENT_FILE + ".tmp", "w") as f: json.dump(d, f)
                os.replace(CONTENT_FILE + ".tmp", CONTENT_FILE)
                _CACHE["data"], _CACHE["error"] = d, None
            except Exception as e:           # deck mid-edit or reshaped: keep the last good copy
                _CACHE["error"] = repr(e)
                if _CACHE["data"] is None and os.path.exists(CONTENT_FILE):
                    _CACHE["data"] = json.load(open(CONTENT_FILE))
        d = json.loads(json.dumps(_CACHE["data"] or {"chapters": [], "total": 0}))
    for c in d["chapters"]:
        if not link_ok(c.get("url")): c["url"] = ""
    d["ver"] = hashlib.sha1(json.dumps(d, sort_keys=True).encode()).hexdigest()[:10]
    return d

# ---------------------------------------------------------------- live state
LOCK = threading.Condition()
def blank(): return {"done": {}, "ch": None, "publish": False, "links": {}, "epoch": 1, "rev": 0, "updated": 0}
try: STATE = {**blank(), **json.load(open(STATE_FILE))}
except Exception: STATE = blank()
VIEWERS = {}
def save():
    STATE["rev"] += 1; STATE["updated"] = time.time()
    with open(STATE_FILE + ".tmp", "w") as f: json.dump(STATE, f)
    os.replace(STATE_FILE + ".tmp", STATE_FILE)
    LOCK.notify_all()
def public_state():
    order = sorted(STATE["done"], key=lambda q: STATE["done"][q])
    return {"done": order, "ch": STATE["ch"], "epoch": STATE["epoch"], "rev": STATE["rev"],
            "links": STATE["links"] if STATE["publish"] else {}, "publish": STATE["publish"],
            "ver": content_ver(), "qa": qa_url()}

_VER = {"t": 0, "v": ""}
def content_ver():
    if time.time() - _VER["t"] > 5: _VER["v"], _VER["t"] = content()["ver"], time.time()
    return _VER["v"]

_QA = {"t": 0, "u": ""}
def qa_url():
    """Public Q&A portal link, only if it is really public (never localhost)."""
    if time.time() - _QA["t"] < 30: return _QA["u"]
    u = os.environ.get("QA_URL", "")
    if not u:
        try: u = open(QA_URL_FILE).read().strip()
        except OSError:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8787/api/info", timeout=1.5) as r: u = json.load(r).get("url", "")
            except Exception: u = ""
    if not re.match(r"https://", u) or re.search(r"localhost|127\.0\.0\.1", u): u = ""
    _QA["t"], _QA["u"] = time.time(), u
    return u

def public_url(host=None):
    """The tunnel URL from url.txt; if that is missing or bogus, the host the request came in on."""
    env = os.environ.get("PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL")
    if env: return env.strip().rstrip("/")
    try: u = open(URL_FILE).read().strip().rstrip("/")
    except OSError: u = ""
    if re.fullmatch(r"https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com", u) or (u and "trycloudflare" not in u): return u
    if host and re.fullmatch(r"[\w.\-]+(:\d+)?", host):
        return ("https://" if host.endswith("trycloudflare.com") else "http://") + host
    return u

# ---------------------------------------------------------------- QR
_QR = {}
def qr(kind, host=None):
    import segno
    u = public_url(host) + "/follow?code=" + CODE
    if (kind, u) not in _QR:
        q = segno.make(u, error="m"); b = io.BytesIO()
        if kind == "svg": q.save(b, kind="svg", scale=8, border=2, dark="#0D263A", xmldecl=False)
        else: q.save(b, kind="png", scale=16, border=3, dark="#0D263A")
        _QR[(kind, u)] = b.getvalue()
        if kind == "png" and u == public_url() + "/follow?code=" + CODE:                     # keep the printable PNG in step with url.txt
            try:
                with open(os.path.join(HERE, "follow-qr.png"), "wb") as f: f.write(_QR[(kind, u)])
            except OSError: pass
    return _QR[(kind, u)]

def write_qr_png():
    try: qr("png")
    except Exception as e: print("QR png failed:", e, flush=True)

# ---------------------------------------------------------------- HTTP
def read(p, mode="r"):
    with open(os.path.join(HERE, p), mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f: return f.read()

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def _send(self, code, body=b"", ctype="text/plain", extra=None):
        if isinstance(body, str): body = body.encode("utf-8")
        if isinstance(body, (dict, list)): body = json.dumps(body).encode(); ctype = "application/json"
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD": self.wfile.write(body)

    def _qs(self): return urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
    def _cookie_key(self):
        m = re.search(COOKIE + r"=([\w\-]+)", self.headers.get("Cookie", ""))
        return m.group(1) if m else ""
    def _is_presenter(self):
        return key_ok(self.headers.get("X-Presenter-Key", "")) or key_ok(self._cookie_key())
    def _has_access(self):
        m = re.search(ACOOKIE + r"=([0-9a-f]+)", self.headers.get("Cookie", ""))
        return (m and hmac.compare_digest(m.group(1), ATOKEN)) or self._is_presenter()
    def _acookie(self):
        sec = "; Secure" if (self.headers.get("X-Forwarded-Proto") == "https" or "trycloudflare" in (self.headers.get("Host") or "") or "onrender.com" in (self.headers.get("Host") or "")) else ""
        return f"{ACOOKIE}={ATOKEN}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000{sec}"
    def _login(self, nxt="/", err="", code=200):
        nxt = nxt if (nxt.startswith("/") and not nxt.startswith("//")) else "/"
        page = LOGIN_HTML.replace("__NEXT__", nxt.replace('"', "")).replace("__ERR__", err)
        return self._send(code, page, "text/html; charset=utf-8", {"Referrer-Policy": "no-referrer"})

    def do_HEAD(self): self.do_GET()
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        qs = self._qs()
        # ---- login gate
        if path == "/login": return self._login((qs.get("next") or ["/"])[0])
        if path == "/robots.txt": return self._send(200, "User-agent: *\nDisallow: /\n")
        open_asset = path.startswith("/fonts/") or (path.startswith("/img/") and os.path.basename(path) in OPEN_IMG)
        presenter_link = path in ("/", "/index.html") and key_ok((qs.get("presenter") or [""])[0])
        if not open_asset and not presenter_link:
            c = (qs.get("code") or [""])[0]
            if c and code_ok(c):
                rest = urllib.parse.urlencode({k: v[0] for k, v in qs.items() if k != "code"})
                return self._send(302, "", "text/plain", {"Location": path + ("?" + rest if rest else ""), "Set-Cookie": self._acookie()})
            if not self._has_access():
                if path.startswith("/api/"): return self._send(401, {"error": "access code required"})
                full = path + ("?" + urllib.parse.urlsplit(self.path).query if urllib.parse.urlsplit(self.path).query else "")
                return self._send(302, "", "text/plain", {"Location": "/login?next=" + urllib.parse.quote(full, safe="")})
        if path in ("/", "/index.html"):
            html = open(DECK, encoding="utf-8").read()
            pk = (qs.get("presenter") or [""])[0]
            if key_ok(pk) or (not pk and key_ok(self._cookie_key())):
                js = read("presenter.js").replace("__FOLLOW_URL__", json.dumps(public_url(self.headers.get("Host")) + "/follow?code=" + CODE))
                html = html.replace("</body>", "<script>\n" + js + "\n</script>\n</body>", 1) if "</body>" in html else html + "<script>" + js + "</script>"
                return self._send(200, html, "text/html; charset=utf-8", {
                    "Set-Cookie": f"{COOKIE}={KEY}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=86400",
                    "Referrer-Policy": "no-referrer"})
            if ANCHOR in html: html = html.replace(ANCHOR, STRIP + ANCHOR, 1)
            return self._send(200, html, "text/html; charset=utf-8")
        if path in ("/follow", "/follow/"):
            page = read("follow.html").replace("/*__CONTENT__*/null", json.dumps(content()).replace("</", "<\\/"))
            return self._send(200, page, "text/html; charset=utf-8", {"Referrer-Policy": "no-referrer"})
        if path in ("/api/leads.csv", "/leads.csv"):
            if not self._is_presenter(): return self._send(403, "presenter key required")
            import csv
            out = io.StringIO(); w = csv.writer(out); w.writerow(["when", "name", "email", "department", "ok to follow up", "questions shown at the time"])
            try:
                for line in open(LEADS_FILE, encoding="utf-8"):
                    try: r = json.loads(line)
                    except ValueError: continue
                    w.writerow([r.get("at"), r.get("name"), r.get("email"), r.get("org"), "yes" if r.get("followup") else "no", r.get("shown")])
            except OSError: pass
            return self._send(200, out.getvalue(), "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="bismarck-signups.csv"'})
        if path == "/api/content": return self._send(200, content())
        if path == "/api/state":
            v = (qs.get("v") or [""])[0][:24]
            if v: VIEWERS[v] = time.time()
            with LOCK: s = public_state()
            if self._is_presenter():
                now = time.time(); s["viewers"] = sum(1 for t in list(VIEWERS.values()) if now - t < 12)
                s["parse_error"] = _CACHE["error"]
            return self._send(200, s)
        if path == "/api/stream": return self.stream(qs)
        if path == "/follow-qr.svg": return self._send(200, qr("svg", self.headers.get("Host")), "image/svg+xml")
        if path == "/follow-qr.png": return self._send(200, qr("png", self.headers.get("Host")), "image/png")
        if path == "/robots.txt": return self._send(200, "User-agent: *\nDisallow: /\n")
        if path.startswith("/img/") or path.startswith("/fonts/"):
            base = IMG if path.startswith("/img/") else FONTS
            name = os.path.basename(path); f = os.path.join(base, name)
            if name and not name.startswith(".") and os.path.isfile(f):
                ct = "font/woff2" if name.endswith(".woff2") else (mimetypes.guess_type(f)[0] or "application/octet-stream")
                with open(f, "rb") as fh: data = fh.read()
                return self._send(200, data, ct, {"Cache-Control": "public, max-age=3600"})
        self._send(404, "Not found")

    def stream(self, qs):
        v = (qs.get("v") or [""])[0][:24]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write((":" + " " * 2048 + "\n\n").encode())   # push through proxy buffers
            last = -1; t0 = time.time()
            while time.time() - t0 < 300:                          # client reconnects every 5 min
                with LOCK:
                    if STATE["rev"] == last: LOCK.wait(10)
                    s = public_state(); rev = s["rev"]
                if v: VIEWERS[v] = time.time()
                if rev != last: self.wfile.write(("data: " + json.dumps(s) + "\n\n").encode()); last = rev
                else: self.wfile.write(b"event: ping\ndata: 1\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError): pass

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/login":
            ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
            n = int(self.headers.get("Content-Length") or 0)
            f = urllib.parse.parse_qs(self.rfile.read(min(n, 4096)).decode("utf-8", "ignore")) if n else {}
            nxt = (f.get("next") or ["/"])[0]
            if too_many(ip): return self._login(nxt, "Too many tries. Wait a few minutes.", 429)
            if code_ok((f.get("code") or [""])[0]):
                nxt = nxt if (nxt.startswith("/") and not nxt.startswith("//")) else "/"
                return self._send(303, "", "text/plain", {"Location": nxt, "Set-Cookie": self._acookie()})
            _FAILS.setdefault(ip, []).append(time.time())
            return self._login(nxt, "That code did not work. Try again.", 401)
        if path == "/api/lead":
            if not self._has_access(): return self._send(401, {"error": "access code required"})
            ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
            if too_many("lead:" + ip): return self._send(429, {"error": "slow down"})
            _FAILS.setdefault("lead:" + ip, []).append(time.time())      # 10 sign-ups per address per 10 min
            try:
                n = int(self.headers.get("Content-Length") or 0)
                b = json.loads(self.rfile.read(min(n, 8192)) or b"{}")
            except Exception: return self._send(400, {"error": "bad json"})
            clean = lambda k, m: re.sub(r"[\x00-\x1f<>]", "", str(b.get(k) or "")).strip()[:m]
            rec = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "name": clean("name", 120), "email": clean("email", 160).lower(),
                   "org": clean("org", 160), "followup": bool(b.get("followup")), "shown": len(STATE["done"])}
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", rec["email"]): return self._send(400, {"error": "email"})
            with LOCK:
                with open(LEADS_FILE, "a", encoding="utf-8") as f: f.write(json.dumps(rec) + "\n")
            return self._send(200, {"ok": True})
        if path not in ("/api/state", "/api/reset"): return self._send(404, "Not found")
        if not self._is_presenter(): return self._send(403, {"error": "presenter key required"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 65536)) or b"{}") if n else {}
        except Exception: return self._send(400, {"error": "bad json"})
        with LOCK:
            if path == "/api/reset":
                STATE.update(done={}, ch=None, epoch=STATE["epoch"] + 1); save()
                return self._send(200, public_state())
            if "epoch" in body and body["epoch"] != STATE["epoch"]:
                return self._send(409, {"error": "state was reset", "epoch": STATE["epoch"]})
            if "done" in body:
                want = {q for q in body["done"] if isinstance(q, str) and re.fullmatch(r"Q\d{1,2}", q)}
                now = time.time()
                STATE["done"] = {q: STATE["done"].get(q, now) for q in sorted(want)}
            if "ch" in body: STATE["ch"] = body["ch"] if isinstance(body["ch"], int) and 0 <= body["ch"] < 50 else None
            if "publish" in body: STATE["publish"] = bool(body["publish"])
            if "links" in body and isinstance(body["links"], dict):
                STATE["links"] = {k: v for k, v in body["links"].items()
                                  if isinstance(k, str) and re.fullmatch(r"Q\d{1,2}", k) and isinstance(v, str) and re.match(r"https?://", v)}
            save()
            return self._send(200, public_state())

    def log_message(self, *a): pass

if __name__ == "__main__":
    content(); write_qr_png()
    host, port = ("0.0.0.0", int(os.environ["PORT"])) if os.environ.get("PORT") else ("127.0.0.1", 8080)
    srv = http.server.ThreadingHTTPServer((host, port), H)
    srv.daemon_threads = True
    print(f"serving on {host}:{port}", flush=True)
    srv.serve_forever()
