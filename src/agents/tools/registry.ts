/**
 * Agent Tool Registry
 * Central registry for all tools available to agents
 */

import { z } from "zod";

/**
 * Tool definition in OpenAI-compatible format
 */
export interface ToolDefinition {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: {
      type: "object";
      properties: Record<string, any>;
      required?: string[];
    };
  };
}

/**
 * Tool handler function signature
 */
export type ToolHandler = (params: {
  userId: number;
  args: Record<string, any>;
}) => Promise<string>;

/**
 * Registered tool with schema and handler
 */
interface RegisteredTool {
  definition: ToolDefinition;
  handler: ToolHandler;
  schema: z.ZodObject<any>;
}

/**
 * Tool Registry
 * Manages all available tools and their handlers
 */
export class ToolRegistry {
  private tools: Map<string, RegisteredTool> = new Map();

  /**
   * Register a new tool
   */
  register(
    definition: ToolDefinition,
    schema: z.ZodObject<any>,
    handler: ToolHandler
  ): void {
    const name = definition.function.name;

    if (this.tools.has(name)) {
      throw new Error(`Tool ${name} is already registered`);
    }

    this.tools.set(name, { definition, schema, handler });
  }

  /**
   * Execute a tool by name
   */
  async execute(
    toolName: string,
    userId: number,
    args: Record<string, any>
  ): Promise<string> {
    const tool = this.tools.get(toolName);

    if (!tool) {
      return `Error: Tool ${toolName} not found`;
    }

    try {
      // Validate arguments
      const validatedArgs = tool.schema.parse(args);

      // Execute handler
      const result = await tool.handler({ userId, args: validatedArgs });

      return result;
    } catch (error) {
      if (error instanceof z.ZodError) {
        return `Error: Invalid arguments for ${toolName}: ${error.message}`;
      }

      const errorMessage =
        error instanceof Error ? error.message : String(error);
      return `Error executing ${toolName}: ${errorMessage}`;
    }
  }

  /**
   * Get tool definitions for a list of tool names
   */
  getDefinitions(toolNames: string[]): ToolDefinition[] {
    const definitions: ToolDefinition[] = [];

    for (const name of toolNames) {
      const tool = this.tools.get(name);
      if (tool) {
        definitions.push(tool.definition);
      }
    }

    return definitions;
  }

  /**
   * Get all registered tool names
   */
  getRegisteredTools(): string[] {
    return Array.from(this.tools.keys());
  }

  /**
   * Check if a tool exists
   */
  hasTool(name: string): boolean {
    return this.tools.has(name);
  }

  /**
   * Get tool definition by name
   */
  getDefinition(name: string): ToolDefinition | undefined {
    return this.tools.get(name)?.definition;
  }
}

/**
 * Global tool registry instance
 */
export const toolRegistry = new ToolRegistry();
