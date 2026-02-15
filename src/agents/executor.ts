/**
 * Agent Executor
 * Runs the agent loop with tool calling via Vercel AI SDK
 */

import { generateText } from "ai";
import { getDb } from "../db/index.js";
import { agentRuns } from "../db/schema.js";
import { toolRegistry } from "./tools/registry.js";
import type { AgentProfile } from "./profiles.js";

/**
 * Agent execution result
 */
export interface AgentResult {
  status: "completed" | "error" | "max_iterations";
  finalMessage: string;
  toolCallsLog: Array<{
    tool: string;
    arguments: Record<string, any>;
    result: string;
    timestamp: string;
  }>;
  iterations: number;
  error?: string;
}

/**
 * Agent Executor
 * Implements the agent loop with tool calling
 */
export class AgentExecutor {
  private profile: AgentProfile;
  private userId: number;
  private threadId: string;
  private maxIterations: number;

  constructor(
    profile: AgentProfile,
    userId: number,
    threadId: string
  ) {
    this.profile = profile;
    this.userId = userId;
    this.threadId = threadId;
    this.maxIterations = profile.maxIterations || 10;
  }

  /**
   * Execute agent with system prompt and user message
   */
  async execute(systemPrompt: string, userMessage: string): Promise<AgentResult> {
    const db = getDb();

    // Create agent run record
    const agentRun = await db
      .insert(agentRuns)
      .values({
        userId: this.userId,
        gmailThreadId: this.threadId,
        profile: this.profile.name,
        status: "running",
        iterations: 0,
      })
      .returning()
      .get();

    const toolCallsLog: AgentResult["toolCallsLog"] = [];
    let iterations = 0;

    try {
      // Get tool definitions for this profile
      const tools = toolRegistry.getDefinitions(this.profile.tools);

      // Run the agent loop
      const result = await generateText({
        model: this.profile.model as any,
        system: systemPrompt,
        prompt: userMessage,
        tools: tools as any,
        maxToolRoundtrips: this.maxIterations,
        temperature: this.profile.temperature,
        maxTokens: this.profile.maxTokens,
        onStepFinish: (step) => {
          iterations++;

          // Log tool calls
          if (step.toolCalls && step.toolCalls.length > 0) {
            for (const toolCall of step.toolCalls) {
              toolCallsLog.push({
                tool: toolCall.toolName,
                arguments: toolCall.args,
                result: step.toolResults?.find((r: any) => r.toolCallId === toolCall.toolCallId)?.result || "",
                timestamp: new Date().toISOString(),
              });
            }
          }
        },
      });

      // Determine final status
      let status: AgentResult["status"] = "completed";
      if (iterations >= this.maxIterations) {
        status = "max_iterations";
      }

      const agentResult: AgentResult = {
        status,
        finalMessage: result.text,
        toolCallsLog,
        iterations,
      };

      // Update agent run record
      await db
        .update(agentRuns)
        .set({
          status: agentResult.status,
          toolCallsLog: JSON.stringify(toolCallsLog),
          finalMessage: agentResult.finalMessage,
          iterations: agentResult.iterations,
          completedAt: new Date().toISOString(),
        })
        .where({ id: agentRun.id });

      return agentResult;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);

      // Update agent run with error
      await db
        .update(agentRuns)
        .set({
          status: "error",
          error: errorMessage,
          toolCallsLog: JSON.stringify(toolCallsLog),
          iterations,
          completedAt: new Date().toISOString(),
        })
        .where({ id: agentRun.id });

      return {
        status: "error",
        finalMessage: "",
        toolCallsLog,
        iterations,
        error: errorMessage,
      };
    }
  }
}
