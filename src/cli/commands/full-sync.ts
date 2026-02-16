/**
 * Full Sync Trigger
 * Triggers a complete inbox sync via API
 */

import chalk from "chalk";

interface FullSyncOptions {
  reset?: boolean;
  url: string;
  user?: string;
  password?: string;
}

export async function fullSync(options: FullSyncOptions) {
  console.log(chalk.bold.cyan("\n🔄 Full Inbox Sync\n"));

  if (options.reset) {
    console.log(chalk.yellow("⚠️  Reset flag enabled - will clear database first"));
    const confirmReset = confirm("Are you sure you want to reset the database?");
    if (!confirmReset) {
      console.log(chalk.gray("Aborted"));
      process.exit(0);
    }

    // Call reset endpoint first
    console.log(chalk.gray("Calling /api/reset..."));
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };

      if (options.user && options.password) {
        const auth = Buffer.from(`${options.user}:${options.password}`).toString("base64");
        headers["Authorization"] = `Basic ${auth}`;
      }

      const resetRes = await fetch(`${options.url}/api/reset`, {
        method: "POST",
        headers,
      });

      if (!resetRes.ok) {
        console.log(chalk.red(`❌ Reset failed: ${resetRes.statusText}`));
        process.exit(1);
      }

      const resetData = await resetRes.json();
      console.log(chalk.green("✅ Database reset complete"));
      console.log(chalk.gray(`   Jobs deleted: ${resetData.jobs_deleted || 0}`));
      console.log(chalk.gray(`   Emails deleted: ${resetData.emails_deleted || 0}`));
      console.log(chalk.gray(`   Events deleted: ${resetData.events_deleted || 0}`));
    } catch (error) {
      console.log(chalk.red(`❌ Reset error: ${error}`));
      process.exit(1);
    }
  }

  // Trigger full sync
  console.log(chalk.gray("\nCalling /api/sync?full=true..."));

  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (options.user && options.password) {
      const auth = Buffer.from(`${options.user}:${options.password}`).toString("base64");
      headers["Authorization"] = `Basic ${auth}`;
    }

    const syncRes = await fetch(`${options.url}/api/sync?full=true`, {
      method: "POST",
      headers,
    });

    if (!syncRes.ok) {
      console.log(chalk.red(`❌ Sync failed: ${syncRes.statusText}`));
      const text = await syncRes.text();
      console.log(chalk.gray(text));
      process.exit(1);
    }

    const syncData = await syncRes.json();
    console.log(chalk.green("\n✅ Full sync triggered"));
    console.log(chalk.gray(`   Job ID: ${syncData.job_id || "N/A"}`));
    console.log(chalk.gray(`   Status: ${syncData.status || "queued"}`));
    console.log(chalk.gray("\n   Monitor server logs for progress"));
  } catch (error) {
    console.log(chalk.red(`❌ Sync error: ${error}`));
    process.exit(1);
  }

  console.log(chalk.bold.green("\n✅ Sync initiated\n"));
}
