"""Vercel entrypoint – re-exports the FastAPI app and adds an Asphalt-themed dashboard."""
from __future__ import annotations

import datetime as _dt
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Bookaboo – Restaurant Reservation API",
    description="Voice-activated restaurant reservation system for Israel.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Asphalt Dashboard (dark themed HTML served at /)
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Bookaboo – Asphalt Dashboard</title>
<style>
  :root {
    --bg: #1a1a2e;
    --surface: #16213e;
    --card: #0f3460;
    --accent: #e94560;
    --accent2: #533483;
    --text: #eaeaea;
    --muted: #8892b0;
    --success: #00d2d3;
    --border: #233554;
    --radius: 14px;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }
  .topbar {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 16px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .topbar h1 { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.5px; }
  .topbar h1 span { color: var(--accent); }
  .topbar .badge {
    background: var(--success);
    color: #000;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .container { max-width: 1200px; margin: 0 auto; padding: 32px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; margin-bottom: 32px; }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    transition: transform 0.2s, box-shadow 0.2s;
  }
  .card:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.3); }
  .card .label { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
  .card .value { font-size: 2rem; font-weight: 700; }
  .card .sub { font-size: 0.85rem; color: var(--muted); margin-top: 4px; }
  .card.accent { border-left: 4px solid var(--accent); }
  .card.accent2 { border-left: 4px solid var(--accent2); }
  .card.success { border-left: 4px solid var(--success); }
  .section-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 16px; color: var(--muted); }
  .endpoint-list { list-style: none; }
  .endpoint-list li {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 14px;
    transition: background 0.2s;
  }
  .endpoint-list li:hover { background: var(--card); }
  .method {
    font-size: 0.75rem;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 6px;
    min-width: 52px;
    text-align: center;
  }
  .method.get { background: rgba(0,210,211,0.15); color: var(--success); }
  .method.post { background: rgba(233,69,96,0.15); color: var(--accent); }
  .path { font-family: 'JetBrains Mono', monospace; font-weight: 500; }
  .desc { color: var(--muted); font-size: 0.85rem; margin-left: auto; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .footer { text-align: center; padding: 40px 0 20px; color: var(--muted); font-size: 0.8rem; }
  .try-btn {
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 10px 24px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    font-size: 0.9rem;
    transition: opacity 0.2s;
  }
  .try-btn:hover { opacity: 0.85; }
  .hero {
    text-align: center;
    padding: 40px 0 32px;
  }
  .hero h2 { font-size: 2rem; font-weight: 800; margin-bottom: 8px; }
  .hero p { color: var(--muted); max-width: 500px; margin: 0 auto; }
</style>
</head>
<body>
<div class="topbar">
  <h1>Bookaboo <span>Asphalt</span></h1>
  <span class="badge">LIVE</span>
</div>
<div class="container">
  <div class="hero">
    <h2>Restaurant Reservation API</h2>
    <p>Voice-activated restaurant booking for Israel, powered by Ontopo API. Search, check availability, and reserve with natural language.</p>
  </div>

  <div class="grid">
    <div class="card accent">
      <div class="label">Status</div>
      <div class="value" id="status">Checking…</div>
      <div class="sub">API health endpoint</div>
    </div>
    <div class="card accent2">
      <div class="label">Version</div>
      <div class="value">1.0.0</div>
      <div class="sub">Bookaboo release</div>
    </div>
    <div class="card success">
      <div class="label">Region</div>
      <div class="value">Israel</div>
      <div class="sub">Ontopo restaurant network</div>
    </div>
  </div>

  <div class="section-title">API Endpoints</div>
  <ul class="endpoint-list">
    <li>
      <span class="method get">GET</span>
      <span class="path">/health</span>
      <span class="desc">Health check</span>
    </li>
    <li>
      <span class="method post">POST</span>
      <span class="path">/reserve</span>
      <span class="desc">Full reservation from natural language</span>
    </li>
    <li>
      <span class="method post">POST</span>
      <span class="path">/search</span>
      <span class="desc">Search restaurants by name</span>
    </li>
    <li>
      <span class="method post">POST</span>
      <span class="path">/availability</span>
      <span class="desc">Check table availability</span>
    </li>
    <li>
      <span class="method get">GET</span>
      <span class="path">/reservations</span>
      <span class="desc">List saved reservations</span>
    </li>
    <li>
      <span class="method get">GET</span>
      <span class="path">/docs</span>
      <span class="desc">Interactive Swagger docs</span>
    </li>
  </ul>

  <div style="text-align:center;margin-top:32px;">
    <a href="/docs"><button class="try-btn">Open API Docs</button></a>
  </div>

  <div class="footer">
    Bookaboo Asphalt Dashboard &middot; Powered by FastAPI on Vercel
  </div>
</div>
<script>
fetch('/health').then(r=>r.json()).then(d=>{
  document.getElementById('status').textContent=d.status==='ok'?'Online':'Error';
  document.getElementById('status').style.color=d.status==='ok'?'#00d2d3':'#e94560';
}).catch(()=>{
  document.getElementById('status').textContent='Offline';
  document.getElementById('status').style.color='#e94560';
});
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    """Serve the Asphalt-themed dashboard."""
    return DASHBOARD_HTML


# ---------------------------------------------------------------------------
# Import and mount all API routes from api_server
# ---------------------------------------------------------------------------
try:
    from api_server import app as _original_app
    for route in _original_app.routes:
        if hasattr(route, "path") and route.path != "/":
            app.routes.append(route)
except ImportError:
    # Fallback: define minimal endpoints if api_server can't be imported
    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok", "service": "bookaboo", "mode": "standalone"}
