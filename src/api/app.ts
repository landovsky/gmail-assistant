import { Hono } from "hono";
import { logger } from "hono/logger";
import { cors } from "hono/cors";
import { healthRoutes } from "./routes/health.js";
import { userRoutes } from "./routes/users.js";
import { authRoutes } from "./routes/auth.js";
import { syncRoutes } from "./routes/sync.js";
import { watchRoutes } from "./routes/watch.js";
import { briefingRoutes } from "./routes/briefing.js";
import { debugRoutes } from "./routes/debug.js";
import { webhookRoutes } from "./routes/webhook.js";
import { basicAuth } from "./middleware/auth.js";

export const app = new Hono();

// Middleware
app.use("*", logger());
app.use("*", cors());

// Public routes (no auth required)
app.route("/api/health", healthRoutes);
app.route("/webhook", webhookRoutes);

// Protected routes (auth required)
app.use("/api/*", basicAuth);
app.use("/debug/*", basicAuth);

app.route("/api/users", userRoutes);
app.route("/api/auth", authRoutes);
app.route("/api", syncRoutes); // /api/sync and /api/reset
app.route("/api/watch", watchRoutes);
app.route("/api/briefing", briefingRoutes);
app.route("/api", debugRoutes); // /api/debug/emails and /api/emails/:id

// Root redirect
app.get("/", (c) => c.redirect("/debug/emails"));

export default app;
