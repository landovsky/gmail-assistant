import { config } from "dotenv";

config();

export interface AppConfig {
  database: {
    type: "sqlite" | "postgres";
    url: string;
  };
  queue: {
    type: "sqlite" | "bullmq";
    redis?: {
      host: string;
      port: number;
    };
    workers: number;
  };
  scheduler: {
    watchRenewalInterval: number; // ms
    fallbackSyncInterval: number; // ms
    fullSyncInterval: number; // ms
  };
  auth: {
    basicAuth?: {
      username: string;
      password: string;
    };
  };
}

export const appConfig: AppConfig = {
  database: {
    type: (process.env.DB_TYPE as "sqlite" | "postgres") || "sqlite",
    url: process.env.DATABASE_URL || "./data/gmail-assistant.db",
  },
  queue: {
    type: (process.env.QUEUE_TYPE as "sqlite" | "bullmq") || "sqlite",
    redis: process.env.REDIS_URL
      ? {
          host: new URL(process.env.REDIS_URL).hostname,
          port: parseInt(new URL(process.env.REDIS_URL).port || "6379"),
        }
      : undefined,
    workers: parseInt(process.env.WORKER_COUNT || "3"),
  },
  scheduler: {
    watchRenewalInterval: 24 * 60 * 60 * 1000, // 24 hours
    fallbackSyncInterval: 15 * 60 * 1000, // 15 minutes
    fullSyncInterval: 60 * 60 * 1000, // 1 hour
  },
  auth: {
    basicAuth:
      process.env.HTTP_BASIC_USER && process.env.HTTP_BASIC_PASS
        ? {
            username: process.env.HTTP_BASIC_USER,
            password: process.env.HTTP_BASIC_PASS,
          }
        : undefined,
  },
};
