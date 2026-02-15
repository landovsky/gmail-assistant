import { appConfig } from "../../config/index.js";
import { SQLiteJobQueue } from "./sqlite.js";
import { BullMQJobQueue } from "./bullmq.js";
import type { JobQueue } from "./interface.js";

let queueInstance: JobQueue | null = null;

export function getJobQueue(): JobQueue {
  if (!queueInstance) {
    if (appConfig.queue.type === "bullmq") {
      queueInstance = new BullMQJobQueue();
    } else {
      queueInstance = new SQLiteJobQueue();
    }
  }

  return queueInstance;
}

export type { JobQueue } from "./interface.js";
