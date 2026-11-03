import path from "node:path";
import { fileURLToPath } from "node:url";

import compression from "compression";
import express from "express";
import helmet from "helmet";
import { createProxyMiddleware } from "http-proxy-middleware";
import morgan from "morgan";

const PORT = Number(process.env.PORT || 3000);
const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8000";
// Only trust incoming X-Forwarded-For when another proxy (e.g. a TLS terminator) sits in front.
const TRUST_PROXY = process.env.TRUST_PROXY === "true";

const publicDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "public");
const app = express();

app.disable("x-powered-by");
app.set("trust proxy", TRUST_PROXY);
app.use(morgan(process.env.NODE_ENV === "production" ? "combined" : "dev"));

app.use(
  helmet({
    contentSecurityPolicy: {
      useDefaults: true,
      directives: {
        "img-src": ["'self'", "data:", "blob:"],
        "style-src": ["'self'"],
        "upgrade-insecure-requests": null,
      },
    },
    crossOriginEmbedderPolicy: false,
  }),
);

app.get("/healthz", (_req, res) => res.json({ status: "ok" }));

// API and uploaded media are served by the Python backend.
const isBackendPath = (p) => p.startsWith("/api/") || p.startsWith("/media/");
app.use((req, _res, next) => {
  if (!TRUST_PROXY && isBackendPath(req.path)) delete req.headers["x-forwarded-for"];
  next();
});
app.use(
  createProxyMiddleware({
    target: BACKEND_URL,
    pathFilter: (p) => isBackendPath(p),
    xfwd: true,
    proxyTimeout: 30_000,
    timeout: 30_000,
    on: {
      error: (err, _req, res) => {
        console.error("proxy error:", err.message);
        if (res.writeHead && !res.headersSent) {
          res.writeHead(502, { "Content-Type": "application/json" });
        }
        res.end(JSON.stringify({ detail: "Backend unavailable, please try again shortly." }));
      },
    },
  }),
);

app.use(compression());
app.use(
  express.static(publicDir, {
    index: false,
    setHeaders: (res, filePath) => {
      res.setHeader("Cache-Control", filePath.endsWith(".html") ? "no-cache" : "public, max-age=3600");
    },
  }),
);

// Single-page app: every other GET serves the shell; the client router takes over.
app.get("*", (_req, res) => {
  res.setHeader("Cache-Control", "no-cache");
  res.sendFile(path.join(publicDir, "index.html"));
});

const server = app.listen(PORT, () => {
  console.log(`Chirp frontend listening on :${PORT}, proxying API to ${BACKEND_URL}`);
});

for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => {
    console.log(`${signal} received, shutting down`);
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(1), 10_000).unref();
  });
}
