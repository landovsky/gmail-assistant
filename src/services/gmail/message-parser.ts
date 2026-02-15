// Gmail message parser implementation
import type { IGmailMessageParser } from '../../shared/types/api.js';
import { gmail_v1 } from 'googleapis';

/**
 * Gmail message parser implementation
 */
export const messageParser: IGmailMessageParser = {
  parseMessage(message: gmail_v1.Schema$Message) {
    const headers = message.payload?.headers || [];

    return {
      subject: getHeader(headers, 'subject'),
      from: getHeader(headers, 'from'),
      to: getHeader(headers, 'to'),
      date: new Date(getHeader(headers, 'date') || Date.now()),
      body: extractPlainTextBody(message),
      headers: headersToRecord(headers),
    };
  },
};

function getHeader(headers: gmail_v1.Schema$MessagePartHeader[], name: string): string {
  const header = headers.find(h => h.name?.toLowerCase() === name.toLowerCase());
  return header?.value || '';
}

function headersToRecord(headers: gmail_v1.Schema$MessagePartHeader[]): Record<string, string> {
  const record: Record<string, string> = {};
  for (const header of headers) {
    if (header.name && header.value) {
      record[header.name] = header.value;
    }
  }
  return record;
}

export function extractPlainTextBody(message: gmail_v1.Schema$Message): string {
  if (!message.payload) return '';

  if (message.payload.body?.data) {
    return Buffer.from(message.payload.body.data, 'base64url').toString('utf-8');
  }

  function findTextPart(part: gmail_v1.Schema$MessagePart): string | null {
    if (part.mimeType === 'text/plain' && part.body?.data) {
      return Buffer.from(part.body.data, 'base64url').toString('utf-8');
    }
    if (part.parts) {
      for (const subPart of part.parts) {
        const text = findTextPart(subPart);
        if (text) return text;
      }
    }
    return null;
  }

  return findTextPart(message.payload) || '';
}
