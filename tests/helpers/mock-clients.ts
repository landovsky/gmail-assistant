/**
 * Mock Gmail Client and Job Queue for Testing
 */

import type { JobQueue } from '../../src/jobs/queue/interface.js';
import type { Job, JobType, JobPayload } from '../../src/jobs/types.js';

/**
 * Mock Gmail Client with in-memory storage
 */
export class MockGmailClient {
  private messages: Map<string, any> = new Map();
  private drafts: Map<string, any> = new Map();
  private labels: Map<string, string[]> = new Map();
  private threads: Map<string, any> = new Map();

  addMessage(message: any) {
    this.messages.set(message.id, message);

    // Add to thread
    if (!this.threads.has(message.threadId)) {
      this.threads.set(message.threadId, { id: message.threadId, messages: [] });
    }
    this.threads.get(message.threadId)!.messages.push(message);
  }

  async getMessage(messageId: string) {
    const msg = this.messages.get(messageId);
    if (!msg) throw new Error(`Message ${messageId} not found`);
    return msg;
  }

  async getThread(threadId: string) {
    const thread = this.threads.get(threadId);
    if (!thread) throw new Error(`Thread ${threadId} not found`);
    return thread;
  }

  async createDraft(
    threadId: string,
    to: string,
    subject: string,
    body: string,
    inReplyTo?: string
  ) {
    const draftId = `draft-${Date.now()}-${Math.random()}`;
    const messageId = `msg-${draftId}`;

    this.drafts.set(draftId, {
      id: draftId,
      message: {
        id: messageId,
        threadId,
        payload: {
          headers: [
            { name: 'To', value: to },
            { name: 'Subject', value: subject },
            { name: 'In-Reply-To', value: inReplyTo || '' },
          ],
          body: { data: Buffer.from(body).toString('base64') },
        },
      },
    });

    return { draftId, messageId };
  }

  async getDraft(draftId: string) {
    const draft = this.drafts.get(draftId);
    if (!draft) throw new Error(`Draft ${draftId} not found`);
    return draft;
  }

  async trashDraft(draftId: string) {
    this.drafts.delete(draftId);
  }

  async modifyThreadLabels(
    threadId: string,
    modifications: { addLabelIds?: string[]; removeLabelIds?: string[] }
  ) {
    const currentLabels = this.labels.get(threadId) || [];
    const newLabels = [...currentLabels];

    if (modifications.addLabelIds) {
      modifications.addLabelIds.forEach(id => {
        if (!newLabels.includes(id)) newLabels.push(id);
      });
    }

    if (modifications.removeLabelIds) {
      modifications.removeLabelIds.forEach(id => {
        const idx = newLabels.indexOf(id);
        if (idx !== -1) newLabels.splice(idx, 1);
      });
    }

    this.labels.set(threadId, newLabels);
  }

  async listMessages(query: string) {
    return Array.from(this.messages.values());
  }

  getThreadLabels(threadId: string): string[] {
    return this.labels.get(threadId) || [];
  }

  getDrafts(): Map<string, any> {
    return this.drafts;
  }
}

/**
 * Mock Job Queue with in-memory storage
 */
export class MockJobQueue implements JobQueue {
  private jobs: Job[] = [];
  private nextId = 1;

  async enqueue(
    jobType: JobType,
    userId: number,
    payload: JobPayload,
    maxAttempts: number = 3
  ): Promise<number> {
    const job: Job = {
      id: this.nextId++,
      jobType,
      userId,
      payload,
      status: 'pending',
      attempts: 0,
      maxAttempts,
      errorMessage: null,
      createdAt: new Date().toISOString(),
      startedAt: null,
      completedAt: null,
    };

    this.jobs.push(job);
    return job.id;
  }

  async claim(): Promise<Job | null> {
    const job = this.jobs.find(j => j.status === 'pending');
    if (!job) return null;

    job.status = 'running';
    job.startedAt = new Date().toISOString();
    return job;
  }

  async complete(jobId: number): Promise<void> {
    const job = this.jobs.find(j => j.id === jobId);
    if (job) {
      job.status = 'completed';
      job.completedAt = new Date().toISOString();
    }
  }

  async fail(jobId: number, errorMessage: string): Promise<void> {
    const job = this.jobs.find(j => j.id === jobId);
    if (job) {
      job.status = 'failed';
      job.errorMessage = errorMessage;
      job.completedAt = new Date().toISOString();
    }
  }

  async retry(jobId: number, errorMessage: string): Promise<void> {
    const job = this.jobs.find(j => j.id === jobId);
    if (job) {
      job.attempts++;
      job.status = 'pending';
      job.errorMessage = errorMessage;
      job.startedAt = null;
    }
  }

  async cleanup(daysOld: number): Promise<number> {
    const cutoff = Date.now() - daysOld * 24 * 60 * 60 * 1000;
    const before = this.jobs.length;
    this.jobs = this.jobs.filter(j => {
      if (!j.completedAt) return true;
      return new Date(j.completedAt).getTime() > cutoff;
    });
    return before - this.jobs.length;
  }

  async hasPendingJob(
    userId: number,
    jobType: JobType,
    threadId?: string
  ): Promise<boolean> {
    return this.jobs.some(j =>
      j.userId === userId &&
      j.jobType === jobType &&
      j.status === 'pending'
    );
  }

  // Test helpers
  getJobs(): Job[] {
    return this.jobs;
  }

  getPendingJobs(): Job[] {
    return this.jobs.filter(j => j.status === 'pending');
  }

  getCompletedJobs(): Job[] {
    return this.jobs.filter(j => j.status === 'completed');
  }

  clear() {
    this.jobs = [];
    this.nextId = 1;
  }
}
