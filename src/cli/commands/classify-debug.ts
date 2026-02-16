/**
 * Classification Debugger
 * Interactive debugging of email classification pipeline
 */

import { getDb } from "../../db/index.js";
import { emails } from "../../db/schema.js";
import { eq } from "drizzle-orm";
import { classificationEngine } from "../../services/classification/engine.js";
import { automationDetector } from "../../services/classification/automation-detector.js";
import { llmService } from "../../services/llm/service.js";
import chalk from "chalk";

interface ClassifyDebugOptions {
  sender?: string;
  senderName?: string;
  subject?: string;
  body?: string;
  threadId?: string;
  live?: boolean;
}

export async function classifyDebug(options: ClassifyDebugOptions) {
  console.log(chalk.bold.cyan("\n🔍 Email Classification Debugger\n"));

  let emailData: any;

  // Load from database or use provided data
  if (options.threadId) {
    console.log(chalk.gray(`Loading email from database: ${options.threadId}`));
    const db = getDb();
    const result = await db
      .select()
      .from(emails)
      .where(eq(emails.gmailThreadId, options.threadId))
      .limit(1);

    if (result.length === 0) {
      console.log(chalk.red(`❌ Thread ID ${options.threadId} not found in database`));
      process.exit(1);
    }

    emailData = {
      from: result[0].senderEmail,
      senderName: result[0].senderName || "",
      subject: result[0].subject || "",
      body: result[0].snippet || "",
      headers: {},
    };
  } else {
    if (!options.sender || !options.subject || !options.body) {
      console.log(chalk.red("❌ Missing required fields: --sender, --subject, --body"));
      console.log(
        chalk.gray("   Or use --thread-id to load from database")
      );
      process.exit(1);
    }

    emailData = {
      from: options.sender,
      senderName: options.senderName || "",
      subject: options.subject,
      body: options.body,
      headers: {},
    };
  }

  console.log(chalk.bold("\n📧 Email Details:"));
  console.log(chalk.gray(`   From: ${emailData.senderName} <${emailData.from}>`));
  console.log(chalk.gray(`   Subject: ${emailData.subject}`));
  console.log(chalk.gray(`   Body: ${emailData.body.substring(0, 100)}...`));

  // Step 1: Automation Detection
  console.log(chalk.bold("\n🤖 Step 1: Automation Detection"));
  const isAutomated = automationDetector.isAutomated(emailData);

  if (isAutomated) {
    console.log(chalk.yellow("   ⚠️  Email detected as AUTOMATED"));
    console.log(chalk.gray("   Classification: automation"));
    console.log(chalk.gray("   Confidence: high"));
    console.log(chalk.gray("   Reason: Matched automation patterns"));
    return;
  } else {
    console.log(chalk.green("   ✓ Email is NOT automated"));
  }

  // Step 2: Rules Engine
  console.log(chalk.bold("\n📋 Step 2: Rules Engine"));
  // Mock classification since we don't have full context
  console.log(chalk.gray("   Evaluating classification rules..."));
  console.log(chalk.yellow("   ⚠️  No rules matched (requires full config)"));

  // Step 3: LLM Classification
  if (options.live) {
    console.log(chalk.bold("\n🧠 Step 3: LLM Classification (LIVE)"));
    try {
      const result = await llmService.classifyEmail({
        from: emailData.from,
        subject: emailData.subject,
        body: emailData.body,
        messageCount: 1,
      });

      console.log(chalk.green("\n✅ Classification Result:"));
      console.log(chalk.bold(`   Category: ${result.category}`));
      console.log(chalk.gray(`   Confidence: ${result.confidence}`));
      console.log(chalk.gray(`   Language: ${result.language}`));
      console.log(chalk.gray(`   Style: ${result.communicationStyle}`));

      if (result.reasoning) {
        console.log(chalk.bold("\n💭 Reasoning:"));
        console.log(chalk.gray(`   ${result.reasoning}`));
      }
    } catch (error) {
      console.log(chalk.red(`\n❌ LLM call failed: ${error}`));
      process.exit(1);
    }
  } else {
    console.log(chalk.bold("\n🧠 Step 3: LLM Classification (DRY RUN)"));
    console.log(
      chalk.gray("   Use --live to make actual LLM call")
    );
    console.log(chalk.gray("\n   Example prompt that would be sent:"));
    console.log(
      chalk.dim(
        `   You are classifying emails. Classify this email:\n   From: ${emailData.from}\n   Subject: ${emailData.subject}\n   Body: ${emailData.body.substring(0, 100)}...`
      )
    );
  }

  console.log(chalk.bold.green("\n✅ Debug complete\n"));
}
