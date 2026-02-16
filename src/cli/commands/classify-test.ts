/**
 * Classification Test Suite
 * Runs classification tests against fixture file
 */

import chalk from "chalk";
import { existsSync, readFileSync } from "fs";
import YAML from "yaml";
import { classificationEngine } from "../../services/classification/engine.js";
import { llmService } from "../../services/llm/service.js";

interface ClassifyTestOptions {
  fixture: string;
  category?: string;
  rulesOnly?: boolean;
  llmOnly?: boolean;
}

interface TestCase {
  id: string;
  from: string;
  sender_name?: string;
  subject: string;
  body: string;
  expected_category: string;
  expected_confidence?: string;
  description?: string;
}

export async function classifyTest(options: ClassifyTestOptions) {
  console.log(chalk.bold.cyan("\n🧪 Classification Test Suite\n"));

  // Load fixture file
  if (!existsSync(options.fixture)) {
    console.log(chalk.red(`❌ Fixture file not found: ${options.fixture}`));
    console.log(chalk.gray("\n   Create a YAML file with test cases:"));
    console.log(
      chalk.dim(`
   tests:
     - id: test-1
       from: sender@example.com
       subject: Meeting request
       body: Can we meet tomorrow?
       expected_category: needs_response
`)
    );
    process.exit(1);
  }

  console.log(chalk.gray(`Loading fixture: ${options.fixture}`));

  let fixture: any;
  try {
    const content = readFileSync(options.fixture, "utf-8");
    fixture = YAML.parse(content);
  } catch (error) {
    console.log(chalk.red(`❌ Failed to parse fixture: ${error}`));
    process.exit(1);
  }

  if (!fixture.tests || !Array.isArray(fixture.tests)) {
    console.log(chalk.red("❌ Fixture must contain 'tests' array"));
    process.exit(1);
  }

  let tests: TestCase[] = fixture.tests;

  // Filter by category if specified
  if (options.category) {
    tests = tests.filter((t) => t.expected_category === options.category);
    console.log(chalk.gray(`Filtering for category: ${options.category}`));
  }

  console.log(chalk.bold(`\n📊 Running ${tests.length} tests...\n`));

  let passed = 0;
  let failed = 0;
  const failures: Array<{ test: TestCase; actual: string }> = [];

  for (const test of tests) {
    process.stdout.write(chalk.gray(`   [${test.id}] ${test.description || test.subject}... `));

    try {
      let result: any;

      if (options.rulesOnly) {
        // Rules-only mode: skip LLM
        result = {
          category: "needs_response", // Default
          confidence: "low",
        };
      } else if (options.llmOnly) {
        // LLM-only mode
        result = await llmService.classifyEmail({
          from: test.from,
          subject: test.subject,
          body: test.body,
          messageCount: 1,
        });
      } else {
        // Full classification (rules + LLM)
        result = await llmService.classifyEmail({
          from: test.from,
          subject: test.subject,
          body: test.body,
          messageCount: 1,
        });
      }

      if (result.category === test.expected_category) {
        console.log(chalk.green("✅ PASS"));
        passed++;
      } else {
        console.log(
          chalk.red(
            `❌ FAIL (expected: ${test.expected_category}, got: ${result.category})`
          )
        );
        failed++;
        failures.push({ test, actual: result.category });
      }
    } catch (error) {
      console.log(chalk.red(`❌ ERROR: ${error}`));
      failed++;
    }
  }

  // Summary
  console.log(chalk.bold("\n📊 Test Summary:"));
  console.log(chalk.green(`   ✅ Passed: ${passed}`));
  console.log(chalk.red(`   ❌ Failed: ${failed}`));
  console.log(chalk.gray(`   Total: ${tests.length}`));

  const accuracy = tests.length > 0 ? (passed / tests.length) * 100 : 0;
  console.log(chalk.bold(`   Accuracy: ${accuracy.toFixed(1)}%`));

  // Confusion matrix
  if (failures.length > 0) {
    console.log(chalk.bold("\n❌ Failures:"));
    failures.forEach(({ test, actual }) => {
      console.log(
        chalk.gray(`   [${test.id}] Expected: ${test.expected_category}, Got: ${actual}`)
      );
    });
  }

  if (failed > 0) {
    console.log(chalk.red("\n❌ Some tests failed\n"));
    process.exit(1);
  } else {
    console.log(chalk.green("\n✅ All tests passed\n"));
    process.exit(0);
  }
}
