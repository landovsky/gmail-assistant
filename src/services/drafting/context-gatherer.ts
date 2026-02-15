// Context gathering system - finds related email threads for draft context
import { generateContextQueries } from '../llm/service';
import type { EmailMetadata } from '../llm/types';

export interface GmailThread {
  id: string;
  subject: string;
  snippet: string;
  messages?: Array<{
    from: string;
    date: string;
    body: string;
  }>;
}

export interface ContextGatherInput {
  email: EmailMetadata;
  gmailSearch: (query: string) => Promise<GmailThread[]>;
  userId?: number;
}

export interface ContextResult {
  queries: string[];
  threads: GmailThread[];
  formattedContext: string[];
}

/**
 * Gather related email context using LLM-generated Gmail queries
 */
export async function gatherRelatedContext(
  input: ContextGatherInput
): Promise<ContextResult> {
  // Generate Gmail search queries using LLM
  const queries = await generateContextQueries({ email: input.email });

  // Execute each query and collect results
  const allThreads: GmailThread[] = [];
  for (const query of queries) {
    try {
      const threads = await input.gmailSearch(query);
      allThreads.push(...threads);
    } catch (error) {
      console.warn(`Gmail search failed for query "${query}":`, error);
    }
  }

  // Deduplicate by thread ID and limit to 3
  const uniqueThreads = deduplicateThreads(allThreads).slice(0, 3);

  // Format as context blocks
  const formattedContext = uniqueThreads.map(formatThreadAsContext);

  return {
    queries,
    threads: uniqueThreads,
    formattedContext,
  };
}

/**
 * Deduplicate threads by ID
 */
function deduplicateThreads(threads: GmailThread[]): GmailThread[] {
  const seen = new Set<string>();
  const unique: GmailThread[] = [];

  for (const thread of threads) {
    if (!seen.has(thread.id)) {
      seen.add(thread.id);
      unique.push(thread);
    }
  }

  return unique;
}

/**
 * Format thread as context block for prompt
 */
function formatThreadAsContext(thread: GmailThread): string {
  let context = `[Thread: "${thread.subject}"]\n`;

  if (thread.messages && thread.messages.length > 0) {
    // Include up to 2 most recent messages
    const recentMessages = thread.messages.slice(-2);
    for (const msg of recentMessages) {
      context += `From: ${msg.from} (${msg.date})\n`;
      context += `${msg.body.substring(0, 300)}${msg.body.length > 300 ? '...' : ''}\n`;
    }
  } else if (thread.snippet) {
    context += thread.snippet;
  }

  return context;
}
