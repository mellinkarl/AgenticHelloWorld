// Simple Express proxy to avoid CORS issues in dev/preview.
// Usage: set API_BASE (defaults to http://127.0.0.1:8000) and run `npm run serve`.
import express from "express";
import fetch from "node-fetch";

const API_BASE = process.env.API_BASE || "http://127.0.0.1:8000";
const PORT = process.env.PORT || 8787;

const app = express();
app.use(express.json());

// Proxy JSON POST to /invoke
app.post("/invoke", async (req, res) => {
  try {
    const r = await fetch(API_BASE + "/invoke", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body || {}),
    });
    const j = await r.json();
    res.status(r.status).json(j);
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

// Proxy GET endpoints by path
for (const p of ["/state/", "/debug_state/", "/debug/cpc"]) {
  app.get(p + "*", async (req, res) => {
    const url = API_BASE + req.originalUrl;
    try {
      const r = await fetch(url);
      const j = await r.json();
      res.status(r.status).json(j);
    } catch (e) {
      res.status(500).json({ error: String(e) });
    }
  });
}

// Proxy file upload to /upload-file
app.post("/upload-file", async (req, res) => {
  // Let the browser talk directly to FastAPI for multipart in dev (simpler).
  res.status(400).json({ error: "Proxy for /upload-file not implemented. Use Vite dev directly against FastAPI." });
});

app.listen(PORT, () => {
  console.log(`[amie-proxy] listening on http://localhost:${PORT} → ${API_BASE}`);
});
