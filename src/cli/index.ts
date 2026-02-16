#!/usr/bin/env node
/**
 * Gmail Assistant CLI
 * Command-line tools for debugging, testing, and administration
 */

import { Command } from "commander";
import { classifyDebug } from "./commands/classify-debug.js";
import { fullSync } from "./commands/full-sync.js";
import { dbReset } from "./commands/db-reset.js";
import { labelCleanup } from "./commands/label-cleanup.js";
import { classifyTest } from "./commands/classify-test.js";

const program = new Command();

program
  .name("gmail-cli")
  .description("Gmail Assistant CLI - Tools for debugging, testing, and administration")
  .version("2.0.0");

// Classification Debugger
program
  .command("classify-debug")
  .description("Debug email classification with step-by-step output")
  .option("-s, --sender <email>", "Sender email address")
  .option("-n, --sender-name <name>", "Sender name")
  .option("--subject <text>", "Email subject")
  .option("-b, --body <text>", "Email body text")
  .option("-t, --thread-id <id>", "Database thread ID to debug")
  .option("--live", "Make live LLM call (requires API key)")
  .action(classifyDebug);

// Full Sync Trigger
program
  .command("full-sync")
  .description("Trigger a complete inbox sync")
  .option("--reset", "Clear database before syncing")
  .option("--url <url>", "API URL", "http://localhost:3000")
  .option("--user <username>", "Basic auth username")
  .option("--password <password>", "Basic auth password")
  .action(fullSync);

// Database Reset
program
  .command("db-reset")
  .description("Clear all transient data (jobs, emails, events)")
  .option("--confirm", "Skip confirmation prompt")
  .option("--url <url>", "API URL", "http://localhost:3000")
  .option("--user <username>", "Basic auth username")
  .option("--password <password>", "Basic auth password")
  .action(dbReset);

// Gmail Label Cleanup
program
  .command("label-cleanup")
  .description("Remove AI workflow labels from Gmail messages")
  .option("--dry-run", "Show what would be removed (default)", true)
  .option("--delete", "Actually remove labels")
  .option("--limit <number>", "Max messages to process", "100")
  .action(labelCleanup);

// Classification Test Suite
program
  .command("classify-test")
  .description("Run classification test suite against fixtures")
  .option("-f, --fixture <file>", "Test fixture YAML file", "tests/fixtures/classification.yml")
  .option("-c, --category <name>", "Test specific category only")
  .option("--rules-only", "Test rules engine only (skip LLM)")
  .option("--llm-only", "Test LLM classification only (skip rules)")
  .action(classifyTest);

program.parse();
