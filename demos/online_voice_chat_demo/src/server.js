// server.js
import express from "express";
import cors from "cors";

const app = express();
app.use(cors()); // exclude CORS

app.get("/session", async (req, res) => {
  try {
    const r = await fetch("https://api.openai.com/v1/realtime/client_secrets", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`, 
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        session: {
          type: "realtime",
          model: "gpt-4o-mini-realtime-preview-2024-12-17",
          output_modalities: ["text"],   
        },
      }),
    });

    const text = await r.text();
    console.log("[/session] status =", r.status, "body =", text);

    // penetrate the original text to the frontend to see ERROR
    res.status(r.status).type("application/json").send(text);
  } catch (err) {
    console.error("[/session] exception:", err);
    res.status(500).json({ error: String(err) });
  }
});

app.listen(3000, () => {
  console.log("Backend running on http://localhost:3000");
  if (!process.env.OPENAI_API_KEY) {
    console.warn("⚠️ Missing OPENAI_API_KEY env var.");
  }
});