/**
 * Agent Framework
 * Main entry point for agent system
 */

export { ToolRegistry, toolRegistry } from "./tools/registry.js";
export type { ToolDefinition, ToolHandler } from "./tools/registry.js";

export { registerCoreTools } from "./tools/core.js";

export { AgentRouter } from "./router.js";
export type {
  EmailMetadata,
  RoutingRule,
  RouteDecision,
  RoutingRuleMatch,
} from "./router.js";

export { AgentExecutor } from "./executor.js";
export type { AgentResult } from "./executor.js";

export { ProfileLoader, createDefaultProfileConfig } from "./profiles.js";
export type { AgentProfile, ProfileConfig } from "./profiles.js";

/**
 * Initialize agent framework
 * Call this on application startup
 */
export function initializeAgents(): void {
  registerCoreTools();
  // Additional initialization can be added here
}
