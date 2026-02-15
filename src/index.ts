// Gmail Assistant v2 - Main Entry Point
import { serve } from "@hono/node-server";
import { app } from "./api/app.js";
import { appConfig } from "./config/index.js";
import { getWorkerPool } from "./jobs/worker-pool.js";
import { getScheduler } from "./scheduler/index.js";
import { runMigrations } from "./db/migrate.js";

const port = parseInt(process.env.PORT || "3000");
const host = process.env.HOST || "0.0.0.0";

async function main() {
  console.log("Gmail Assistant v2 starting...");

  // Run database migrations
  console.log("Running database migrations...");
  runMigrations(appConfig.database.url);

  // Start worker pool
  console.log("Starting worker pool...");
  const workerPool = getWorkerPool();
  await workerPool.start();

  // Start scheduler
  console.log("Starting scheduler...");
  const scheduler = getScheduler();
  await scheduler.start();

  // Start HTTP server
  console.log(`Starting HTTP server on http://${host}:${port}`);
  serve({
    fetch: app.fetch,
    port,
    hostname: host,
  });

  console.log("Gmail Assistant v2 ready!");
}

main().catch((error) => {
  console.error("Failed to start application:", error);
  process.exit(1);
});

// Graceful shutdown
process.on("SIGTERM", async () => {
  console.log("SIGTERM received, shutting down gracefully...");
  const workerPool = getWorkerPool();
  const scheduler = getScheduler();

  await scheduler.stop();
  await workerPool.stop();

  process.exit(0);
});
