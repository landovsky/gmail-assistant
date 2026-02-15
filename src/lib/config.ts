// Configuration management with environment variable overrides
import { z } from 'zod';
import { readFileSync } from 'fs';
import { parse } from 'yaml';
import 'dotenv/config';

const ConfigSchema = z.object({
  server: z.object({
    host: z.string().default('0.0.0.0'),
    port: z.number().default(3000),
    workers: z.number().default(3),
  }),
  database: z.object({
    url: z.string().default('sqlite://data/inbox.db'),
  }),
  jobQueue: z.object({
    type: z.enum(['sqlite', 'bullmq']).default('sqlite'),
    redis: z.object({
      host: z.string().default('localhost'),
      port: z.number().default(6379),
    }).optional(),
  }),
  auth: z.object({
    basicUser: z.string().optional(),
    basicPassword: z.string().optional(),
  }),
  llm: z.object({
    classificationModel: z.string().default('google/gemini-2.0-flash-exp'),
    draftModel: z.string().default('anthropic/claude-3-7-sonnet-20250219'),
    contextModel: z.string().default('google/gemini-2.0-flash-exp'),
  }),
  gmail: z.object({
    credentialsPath: z.string().default('credentials.json'),
    tokenPath: z.string().default('token.json'),
    pubsubTopic: z.string().optional(),
  }),
});

export type Config = z.infer<typeof ConfigSchema>;

function loadConfig(): Config {
  let baseConfig = {};

  // Try to load YAML config file
  try {
    const yamlContent = readFileSync('config/app.yml', 'utf-8');
    baseConfig = parse(yamlContent);
  } catch (error) {
    console.warn('No config/app.yml found, using defaults and environment variables');
  }

  // Override with environment variables
  const envConfig = {
    server: {
      host: process.env.HOST,
      port: process.env.PORT ? parseInt(process.env.PORT) : undefined,
      workers: process.env.WORKERS ? parseInt(process.env.WORKERS) : undefined,
    },
    database: {
      url: process.env.DATABASE_URL,
    },
    jobQueue: {
      type: process.env.JOB_QUEUE_TYPE as 'sqlite' | 'bullmq' | undefined,
      redis: {
        host: process.env.REDIS_HOST,
        port: process.env.REDIS_PORT ? parseInt(process.env.REDIS_PORT) : undefined,
      },
    },
    auth: {
      basicUser: process.env.HTTP_BASIC_USER,
      basicPassword: process.env.HTTP_BASIC_PASSWORD,
    },
    llm: {
      classificationModel: process.env.LLM_CLASSIFICATION_MODEL,
      draftModel: process.env.LLM_DRAFT_MODEL,
      contextModel: process.env.LLM_CONTEXT_MODEL,
    },
    gmail: {
      credentialsPath: process.env.GMAIL_CREDENTIALS_PATH,
      tokenPath: process.env.GMAIL_TOKEN_PATH,
      pubsubTopic: process.env.PUBSUB_TOPIC,
    },
  };

  // Deep merge, removing undefined values
  const merged = deepMerge(baseConfig, removeUndefined(envConfig));

  return ConfigSchema.parse(merged);
}

function deepMerge(target: any, source: any): any {
  const output = { ...target };
  for (const key in source) {
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
      output[key] = deepMerge(target[key] || {}, source[key]);
    } else {
      output[key] = source[key];
    }
  }
  return output;
}

function removeUndefined(obj: any): any {
  if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
    const clean: any = {};
    for (const key in obj) {
      const value = removeUndefined(obj[key]);
      if (value !== undefined) {
        clean[key] = value;
      }
    }
    return Object.keys(clean).length > 0 ? clean : undefined;
  }
  return obj;
}

export const config = loadConfig();
