/**
 * Gmail Label Cleanup
 * Removes AI workflow labels from Gmail messages
 */

import chalk from "chalk";
import { getAuthenticatedClient } from "../../services/gmail/auth.js";
import { GmailClient } from "../../services/gmail/client.js";
import { getDb } from "../../db/index.js";
import { userLabels } from "../../db/schema.js";

interface LabelCleanupOptions {
  dryRun?: boolean;
  delete?: boolean;
  limit: string;
}

export async function labelCleanup(options: LabelCleanupOptions) {
  console.log(chalk.bold.cyan("\n🏷️  Gmail Label Cleanup\n"));

  const isDryRun = !options.delete;
  const limit = parseInt(options.limit);

  if (isDryRun) {
    console.log(chalk.yellow("⚠️  DRY RUN MODE - No changes will be made"));
    console.log(chalk.gray("   Use --delete to actually remove labels\n"));
  }

  console.log(chalk.gray("Authenticating with Gmail..."));

  let client: GmailClient;
  try {
    const oauth2Client = await getAuthenticatedClient(
      process.env.MASTER_KEY_PATH || "config/master.key",
      process.env.TOKEN_PATH || "config/token.json"
    );
    client = new GmailClient(oauth2Client);
  } catch (error) {
    console.log(chalk.red(`❌ Authentication failed: ${error}`));
    process.exit(1);
  }

  console.log(chalk.green("✅ Authenticated\n"));

  // Load AI labels from database
  console.log(chalk.gray("Loading AI labels from database..."));
  const db = getDb();
  const labels = await db.select().from(userLabels);

  if (labels.length === 0) {
    console.log(chalk.yellow("⚠️  No labels found in database"));
    process.exit(0);
  }

  console.log(chalk.green(`✅ Found ${labels.length} AI labels:\n`));
  labels.forEach((label) => {
    console.log(chalk.gray(`   - ${label.gmailLabelName} (${label.gmailLabelId})`));
  });

  // Search for messages with any of these labels
  console.log(chalk.gray("\nSearching for messages with AI labels..."));

  const labelIds = labels.map((l) => l.gmailLabelId);
  let totalMessages = 0;
  const messagesToClean: Array<{ id: string; threadId: string }> = [];

  for (const labelId of labelIds) {
    try {
      const messages = await client.listMessages({
        labelIds: [labelId],
        maxResults: limit,
      });

      if (messages.length > 0) {
        console.log(
          chalk.gray(`   Found ${messages.length} messages with label ${labelId}`)
        );
        totalMessages += messages.length;

        messages.forEach((msg) => {
          if (msg.id && msg.threadId) {
            messagesToClean.push({ id: msg.id, threadId: msg.threadId });
          }
        });
      }
    } catch (error) {
      console.log(chalk.yellow(`   ⚠️  Could not search label ${labelId}: ${error}`));
    }
  }

  console.log(chalk.bold(`\n📊 Total messages to process: ${totalMessages}`));

  if (totalMessages === 0) {
    console.log(chalk.green("\n✅ No messages to clean"));
    process.exit(0);
  }

  if (isDryRun) {
    console.log(chalk.gray("\nPreview (first 10):"));
    messagesToClean.slice(0, 10).forEach((msg) => {
      console.log(chalk.gray(`   - Message ${msg.id} (Thread ${msg.threadId})`));
    });

    console.log(chalk.yellow("\n⚠️  DRY RUN - No labels were removed"));
    console.log(chalk.gray("   Run with --delete to remove labels"));
  } else {
    console.log(chalk.yellow("\n⚠️  Removing labels..."));

    let removed = 0;
    for (const msg of messagesToClean) {
      try {
        await client.modifyLabels(msg.id, {
          removeLabelIds: labelIds,
        });
        removed++;
      } catch (error) {
        console.log(chalk.red(`   ❌ Failed to remove labels from ${msg.id}`));
      }
    }

    console.log(chalk.green(`\n✅ Removed labels from ${removed} messages`));
  }

  console.log(chalk.bold.green("\n✅ Cleanup complete\n"));
}
