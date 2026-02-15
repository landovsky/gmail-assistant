/**
 * Database Test Fixtures and Seed Data
 * Provides sample data for development and testing
 */

import type { NewUser, NewEmail, NewUserLabel, NewUserSetting, NewSyncState } from "../schema.js";

/**
 * Sample Users
 */
export const sampleUsers: NewUser[] = [
  {
    email: "alice@example.com",
    displayName: "Alice Johnson",
    isActive: true,
    onboardedAt: "2025-01-15 10:00:00",
  },
  {
    email: "bob@example.com",
    displayName: "Bob Smith",
    isActive: true,
    onboardedAt: "2025-01-20 14:30:00",
  },
  {
    email: "charlie@example.com",
    displayName: "Charlie Davis",
    isActive: false,
    onboardedAt: null,
  },
];

/**
 * Sample Gmail Labels for User 1 (Alice)
 */
export const sampleLabelsUser1: Omit<NewUserLabel, "userId">[] = [
  {
    labelKey: "needs_response",
    gmailLabelId: "Label_1",
    gmailLabelName: "📝 Needs Response",
  },
  {
    labelKey: "action_required",
    gmailLabelId: "Label_2",
    gmailLabelName: "⚠️ Action Required",
  },
  {
    labelKey: "payment_request",
    gmailLabelId: "Label_3",
    gmailLabelName: "💰 Payment Request",
  },
  {
    labelKey: "fyi",
    gmailLabelId: "Label_4",
    gmailLabelName: "📖 FYI",
  },
  {
    labelKey: "waiting",
    gmailLabelId: "Label_5",
    gmailLabelName: "⏳ Waiting",
  },
  {
    labelKey: "outbox",
    gmailLabelId: "Label_6",
    gmailLabelName: "📤 Outbox",
  },
  {
    labelKey: "rework",
    gmailLabelId: "Label_7",
    gmailLabelName: "🔄 Rework",
  },
  {
    labelKey: "done",
    gmailLabelId: "Label_8",
    gmailLabelName: "✅ Done",
  },
];

/**
 * Sample User Settings for User 1 (Alice)
 */
export const sampleSettingsUser1: Omit<NewUserSetting, "userId">[] = [
  {
    settingKey: "communication_styles",
    settingValue: JSON.stringify({
      formal: "Dear [name],\n\n[content]\n\nBest regards,\nAlice Johnson",
      business: "Hi [name],\n\n[content]\n\nRegards,\nAlice",
      informal: "Hey [name]!\n\n[content]\n\nCheers,\nAlice",
    }),
  },
  {
    settingKey: "contacts",
    settingValue: JSON.stringify({
      overrides: {
        "boss@company.com": { style: "formal" },
        "team@company.com": { style: "business" },
      },
      blacklist: ["spam@example.com", "noreply@automated.com"],
    }),
  },
  {
    settingKey: "sign_off_name",
    settingValue: JSON.stringify("Alice Johnson"),
  },
  {
    settingKey: "default_language",
    settingValue: JSON.stringify("en"),
  },
];

/**
 * Sample Sync State for User 1 (Alice)
 */
export const sampleSyncStateUser1: Omit<NewSyncState, "userId"> = {
  lastHistoryId: "12345678",
  lastSyncAt: "2025-02-15 08:00:00",
  watchExpiration: "2025-02-16 08:00:00",
  watchResourceId: "projects/gmail-assistant/subscriptions/alice-watch",
};

/**
 * Sample Emails for User 1 (Alice)
 */
export const sampleEmailsUser1: Omit<NewEmail, "userId">[] = [
  {
    gmailThreadId: "thread_001",
    gmailMessageId: "msg_001",
    senderEmail: "client@business.com",
    senderName: "Sarah Client",
    subject: "Project Update Request",
    snippet: "Hi Alice, could you provide an update on the Q1 deliverables?",
    receivedAt: "2025-02-15 09:00:00",
    classification: "needs_response",
    confidence: "high",
    reasoning: "Direct question requiring response about project status",
    detectedLanguage: "en",
    resolvedStyle: "business",
    messageCount: 1,
    status: "pending",
    processedAt: "2025-02-15 09:01:00",
  },
  {
    gmailThreadId: "thread_002",
    gmailMessageId: "msg_002",
    senderEmail: "vendor@supplies.com",
    senderName: "Acme Supplies",
    subject: "Invoice #12345 - Payment Due",
    snippet: "Your invoice for $450.00 is due by February 20, 2025",
    receivedAt: "2025-02-14 15:30:00",
    classification: "payment_request",
    confidence: "high",
    reasoning: "Invoice with payment amount and due date detected",
    detectedLanguage: "en",
    resolvedStyle: "business",
    messageCount: 1,
    status: "pending",
    vendorName: "Acme Supplies",
    processedAt: "2025-02-14 15:31:00",
  },
  {
    gmailThreadId: "thread_003",
    gmailMessageId: "msg_003",
    senderEmail: "newsletter@tech.com",
    senderName: "Tech Weekly",
    subject: "This Week in Technology",
    snippet: "Top 10 tech trends, new AI breakthroughs, and more...",
    receivedAt: "2025-02-15 06:00:00",
    classification: "fyi",
    confidence: "medium",
    reasoning: "Newsletter format, informational content, no action required",
    detectedLanguage: "en",
    resolvedStyle: "informal",
    messageCount: 1,
    status: "pending",
    processedAt: "2025-02-15 06:01:00",
  },
  {
    gmailThreadId: "thread_004",
    gmailMessageId: "msg_005",
    senderEmail: "support@service.com",
    senderName: "Customer Support",
    subject: "Re: Ticket #789 - Still investigating",
    snippet: "We're still looking into your issue. Will update you soon.",
    receivedAt: "2025-02-13 11:00:00",
    classification: "waiting",
    confidence: "high",
    reasoning: "Support team indicated they will follow up, no immediate action needed",
    detectedLanguage: "en",
    resolvedStyle: "business",
    messageCount: 3,
    status: "pending",
    processedAt: "2025-02-13 11:01:00",
  },
  {
    gmailThreadId: "thread_005",
    gmailMessageId: "msg_006",
    senderEmail: "manager@company.com",
    senderName: "John Manager",
    subject: "Meeting Notes - Action Items",
    snippet: "Please review the attached meeting notes and complete your assigned tasks",
    receivedAt: "2025-02-15 10:30:00",
    classification: "action_required",
    confidence: "high",
    reasoning: "Explicit action items assigned, requires user to complete tasks",
    detectedLanguage: "en",
    resolvedStyle: "formal",
    messageCount: 1,
    status: "pending",
    processedAt: "2025-02-15 10:31:00",
  },
  {
    gmailThreadId: "thread_006",
    gmailMessageId: "msg_007",
    senderEmail: "friend@personal.com",
    senderName: "Emily Friend",
    subject: "Dinner plans?",
    snippet: "Hey! Want to grab dinner this weekend?",
    receivedAt: "2025-02-14 18:00:00",
    classification: "needs_response",
    confidence: "high",
    reasoning: "Personal email with direct question",
    detectedLanguage: "en",
    resolvedStyle: "informal",
    messageCount: 1,
    status: "drafted",
    draftId: "draft_001",
    draftedAt: "2025-02-14 18:05:00",
    processedAt: "2025-02-14 18:01:00",
  },
  {
    gmailThreadId: "thread_007",
    gmailMessageId: "msg_008",
    senderEmail: "recruiter@headhunter.com",
    senderName: "Jane Recruiter",
    subject: "Exciting opportunity at TechCorp",
    snippet: "I have a senior position that matches your profile...",
    receivedAt: "2025-02-12 14:00:00",
    classification: "needs_response",
    confidence: "medium",
    reasoning: "Recruitment email, may want to respond or ignore",
    detectedLanguage: "en",
    resolvedStyle: "business",
    messageCount: 1,
    status: "rework_requested",
    draftId: "draft_002",
    reworkCount: 1,
    lastReworkInstruction: "Make the tone more polite but firm in declining",
    draftedAt: "2025-02-12 14:10:00",
    processedAt: "2025-02-12 14:01:00",
  },
];

/**
 * Sample Emails for User 2 (Bob)
 */
export const sampleEmailsUser2: Omit<NewEmail, "userId">[] = [
  {
    gmailThreadId: "thread_101",
    gmailMessageId: "msg_101",
    senderEmail: "ceo@company.com",
    senderName: "CEO",
    subject: "Q1 Strategy Review",
    snippet: "Please prepare your department's Q1 review for the board meeting",
    receivedAt: "2025-02-15 07:00:00",
    classification: "action_required",
    confidence: "high",
    reasoning: "Executive request with deadline, requires preparation",
    detectedLanguage: "en",
    resolvedStyle: "formal",
    messageCount: 1,
    status: "pending",
    processedAt: "2025-02-15 07:01:00",
  },
  {
    gmailThreadId: "thread_102",
    gmailMessageId: "msg_102",
    senderEmail: "accounting@company.com",
    senderName: "Accounting Dept",
    subject: "Expense Report #456 - Rejected",
    snippet: "Your expense report has been rejected. Missing receipts for items 3-5",
    receivedAt: "2025-02-14 12:00:00",
    classification: "action_required",
    confidence: "high",
    reasoning: "Rejection notice requiring correction and resubmission",
    detectedLanguage: "en",
    resolvedStyle: "business",
    messageCount: 2,
    status: "pending",
    processedAt: "2025-02-14 12:01:00",
  },
];

/**
 * Helper: Create full email with user ID
 */
export function createEmail(userId: number, emailTemplate: Omit<NewEmail, "userId">): NewEmail {
  return {
    userId,
    ...emailTemplate,
  };
}

/**
 * Helper: Create full user label with user ID
 */
export function createUserLabel(userId: number, labelTemplate: Omit<NewUserLabel, "userId">): NewUserLabel {
  return {
    userId,
    ...labelTemplate,
  };
}

/**
 * Helper: Create full user setting with user ID
 */
export function createUserSetting(userId: number, settingTemplate: Omit<NewUserSetting, "userId">): NewUserSetting {
  return {
    userId,
    ...settingTemplate,
  };
}

/**
 * Helper: Create full sync state with user ID
 */
export function createSyncState(userId: number, stateTemplate: Omit<NewSyncState, "userId">): NewSyncState {
  return {
    userId,
    ...stateTemplate,
  };
}
