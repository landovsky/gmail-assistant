/**
 * Database Reset
 * Clears all transient data via API
 */

import chalk from "chalk";

interface DbResetOptions {
  confirm?: boolean;
  url: string;
  user?: string;
  password?: string;
}

export async function dbReset(options: DbResetOptions) {
  console.log(chalk.bold.cyan("\n🗑️  Database Reset\n"));

  console.log(chalk.yellow("⚠️  This will delete:"));
  console.log(chalk.gray("   - All jobs"));
  console.log(chalk.gray("   - All emails"));
  console.log(chalk.gray("   - All email events"));
  console.log(chalk.gray("   - All sync state"));
  console.log(chalk.gray("\n   Preserves:"));
  console.log(chalk.gray("   - Users"));
  console.log(chalk.gray("   - User labels"));
  console.log(chalk.gray("   - User settings"));

  if (!options.confirm) {
    const shouldProceed = confirm("\nAre you sure you want to reset the database?");
    if (!shouldProceed) {
      console.log(chalk.gray("Aborted"));
      process.exit(0);
    }
  }

  console.log(chalk.gray("\nCalling /api/reset..."));

  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (options.user && options.password) {
      const auth = Buffer.from(`${options.user}:${options.password}`).toString("base64");
      headers["Authorization"] = `Basic ${auth}`;
    }

    const res = await fetch(`${options.url}/api/reset`, {
      method: "POST",
      headers,
    });

    if (!res.ok) {
      console.log(chalk.red(`❌ Reset failed: ${res.statusText}`));
      const text = await res.text();
      console.log(chalk.gray(text));
      process.exit(1);
    }

    const data = await res.json();
    console.log(chalk.green("\n✅ Database reset complete"));
    console.log(chalk.gray(`   Jobs deleted: ${data.jobs_deleted || 0}`));
    console.log(chalk.gray(`   Emails deleted: ${data.emails_deleted || 0}`));
    console.log(chalk.gray(`   Events deleted: ${data.events_deleted || 0}`));
    console.log(chalk.gray(`   Sync state deleted: ${data.sync_deleted || 0}`));
  } catch (error) {
    console.log(chalk.red(`❌ Reset error: ${error}`));
    process.exit(1);
  }

  console.log(chalk.bold.green("\n✅ Reset complete\n"));
}
