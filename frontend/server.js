
import http from "node:http";
import https from "node:https";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL;
const API_KEY = (process.env.API_KEY || "").replace(/\s/g, "");
const DIST_DIR = path.join(__dirname, "dist");

const mimeTypes = {
  ".html": "text/html",
  ".js": "application/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2"
};

const server = http.createServer((req, res) => {
  if (req.url.startsWith("/api/")) {
    if (!BACKEND_URL || !API_KEY) {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ detail: "Backend configuration missing" }));
      return;
    }

    let targetUrl;

    try {
      targetUrl = new URL(req.url.replace(/^\/api/, ""), BACKEND_URL);
    } catch {
      res.writeHead(500);
      res.end("Invalid backend URL");
      return;
    }

    const transport = targetUrl.protocol === "https:" ? https : http;

    const headers = { ...req.headers };
    delete headers["x-api-key"];
    headers.host = targetUrl.host;
    headers["x-api-key"] = API_KEY;

    const proxyReq = transport.request(
      targetUrl,
      {
        method: req.method,
        headers
      },
      (proxyRes) => {
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(res);
      }
    );

    proxyReq.on("error", () => {
      if (!res.headersSent) {
        res.writeHead(502, { "Content-Type": "application/json" });
      }
      res.end(JSON.stringify({ detail: "Backend unavailable" }));
    });

    req.pipe(proxyReq);
    return;
  }

  let requestedPath;

  try {
    requestedPath = decodeURIComponent(
      new URL(req.url, "http://localhost").pathname
    );
  } catch {
    res.writeHead(400);
    res.end("Invalid URL");
    return;
  }

  const filePath = path.resolve(DIST_DIR, `.${requestedPath}`);
  const relativePath = path.relative(DIST_DIR, filePath);

  if (relativePath.startsWith("..") || path.isAbsolute(relativePath)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  const serveFile =
    fs.existsSync(filePath) && fs.statSync(filePath).isFile()
      ? filePath
      : path.join(DIST_DIR, "index.html");

  fs.readFile(serveFile, (err, content) => {
    if (err) {
      res.writeHead(404);
      res.end("Frontend build not found");
      return;
    }

    const contentType =
      mimeTypes[path.extname(serveFile)] || "application/octet-stream";

    res.writeHead(200, { "Content-Type": contentType });
    res.end(content);
  });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Nimbus PayDesk frontend running on port ${PORT}`);
});
