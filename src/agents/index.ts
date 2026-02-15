/**
 * Agent Framework
 * Main entry point for agent system
 */

export { ToolRegistry, toolRegistry } from './tools/registry.js';
export type { ToolDefinition, ToolHandler, ToolContext } from './tools/registry.js';

import { registerCoreTools } from './tools/core.js';
import { registerPharmacyTools } from './tools/pharmacy.js';
export { registerCoreTools, registerPharmacyTools };

export { AgentRouter } from './router.js';
export type { EmailMetadata, RoutingRule, RouteDecision, RoutingRuleMatch } from './router.js';

export { AgentExecutor } from './executor.js';
export type { AgentResult } from './executor.js';

export { ProfileLoader, createDefaultProfileConfig } from './profiles.js';
export type { AgentProfile, ProfileConfig } from './profiles.js';

/**
 * Initialize agent framework
 * Call this on application startup
 */
export function initializeAgents(): void {
  registerCoreTools();
  registerPharmacyTools();
}
