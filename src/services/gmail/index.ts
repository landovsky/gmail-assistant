// Gmail service exports
export { GmailClient, extractPlainTextBody, getHeader, parseSender } from './client.js';
export { getAuthenticatedClient, getUserEmail } from './auth.js';
export { GmailSyncEngine } from './sync.js';

// Adapter exports (shared API contracts)
export { sync } from './sync-adapter.js';
export { messageParser } from './message-parser.js';
