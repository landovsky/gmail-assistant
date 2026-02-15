/**
 * Agent Profile Loader
 * Loads and manages agent configurations
 */

import { readFileSync } from "fs";
import { resolve } from "path";

/**
 * Agent profile configuration
 */
export interface AgentProfile {
  name: string;
  model: string;
  maxTokens: number;
  temperature: number;
  maxIterations: number;
  systemPromptFile: string;
  tools: string[];
}

/**
 * Profile configuration (from YAML/config)
 */
export interface ProfileConfig {
  profiles: Record<string, Omit<AgentProfile, "name">>;
}

/**
 * Profile Loader
 * Loads agent profiles from configuration
 */
export class ProfileLoader {
  private profiles: Map<string, AgentProfile> = new Map();
  private promptsDir: string;

  constructor(config: ProfileConfig, promptsDir: string = "config/prompts") {
    this.promptsDir = promptsDir;
    this.loadProfiles(config);
  }

  /**
   * Load profiles from configuration
   */
  private loadProfiles(config: ProfileConfig): void {
    for (const [name, profileConfig] of Object.entries(config.profiles)) {
      this.profiles.set(name, {
        name,
        ...profileConfig,
      });
    }
  }

  /**
   * Get profile by name
   */
  getProfile(name: string): AgentProfile | null {
    return this.profiles.get(name) || null;
  }

  /**
   * Load system prompt for a profile
   */
  loadSystemPrompt(profile: AgentProfile): string {
    const promptPath = resolve(this.promptsDir, profile.systemPromptFile);

    try {
      return readFileSync(promptPath, "utf-8");
    } catch (error) {
      throw new Error(
        `Failed to load system prompt for profile ${profile.name}: ${error}`
      );
    }
  }

  /**
   * Get all profile names
   */
  getProfileNames(): string[] {
    return Array.from(this.profiles.keys());
  }

  /**
   * Validate that a profile has all required tools
   */
  validateProfile(profile: AgentProfile, availableTools: string[]): boolean {
    for (const toolName of profile.tools) {
      if (!availableTools.includes(toolName)) {
        console.warn(
          `Profile ${profile.name} requires tool ${toolName} which is not registered`
        );
        return false;
      }
    }
    return true;
  }
}

/**
 * Create default profile configuration
 */
export function createDefaultProfileConfig(): ProfileConfig {
  return {
    profiles: {
      pharmacy: {
        model: "anthropic/claude-3-5-sonnet-20241022",
        maxTokens: 4096,
        temperature: 0.3,
        maxIterations: 10,
        systemPromptFile: "pharmacy.txt",
        tools: [
          "search_drugs",
          "manage_reservation",
          "web_search",
          "send_reply",
          "create_draft",
          "escalate",
        ],
      },
    },
  };
}
