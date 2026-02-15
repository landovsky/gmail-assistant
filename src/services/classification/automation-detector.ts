// Tier 1: Rule-based automation detection

const AUTOMATION_PATTERNS = [
  'noreply',
  'no-reply',
  'do-not-reply',
  'donotreply',
  'mailer-daemon',
  'postmaster',
  'automated',
  'notification',
  'notifications',
  'updates',
  'alerts',
  'news',
];

export interface AutomationCheckInput {
  senderEmail: string;
  headers?: Record<string, string>;
  blacklist?: string[];
}

export interface AutomationCheckResult {
  isAutomated: boolean;
  reason?: string;
}

function checkSenderPatterns(email: string): boolean {
  const lowercase = email.toLowerCase();
  return AUTOMATION_PATTERNS.some((pattern) => lowercase.includes(pattern));
}

function checkAutomationHeaders(headers: Record<string, string>): boolean {
  const autoSubmitted = headers['auto-submitted'] || headers['Auto-Submitted'];
  if (autoSubmitted?.startsWith('auto-')) return true;

  const precedence = headers['precedence'] || headers['Precedence'];
  if (['bulk', 'list', 'junk'].includes(precedence?.toLowerCase() || '')) return true;

  if (headers['list-unsubscribe'] || headers['List-Unsubscribe'] ||
      headers['list-id'] || headers['List-Id']) return true;

  if (headers['x-auto-response-suppress'] || headers['X-Auto-Response-Suppress']) return true;

  return false;
}

function checkBlacklist(email: string, patterns: string[]): boolean {
  for (const pattern of patterns) {
    const regex = new RegExp('^' + pattern.replace(/\*/g, '.*').replace(/\?/g, '.') + '$', 'i');
    if (regex.test(email)) return true;
  }
  return false;
}

export function detectAutomation(input: AutomationCheckInput): AutomationCheckResult {
  if (input.blacklist && checkBlacklist(input.senderEmail, input.blacklist)) {
    return { isAutomated: true, reason: 'blacklist' };
  }

  if (checkSenderPatterns(input.senderEmail)) {
    return { isAutomated: true, reason: 'sender_pattern' };
  }

  if (input.headers && checkAutomationHeaders(input.headers)) {
    return { isAutomated: true, reason: 'automation_headers' };
  }

  return { isAutomated: false };
}
