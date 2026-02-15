// Gmail label management and provisioning
import { GmailClient } from './client.js';

export interface LabelMapping {
  key: string;
  name: string;
  gmailLabelId: string;
}

/**
 * AI label definitions
 * These are provisioned during user onboarding
 */
export const AI_LABELS = {
  parent: {
    key: 'ai',
    name: '🤖 AI',
  },
  children: [
    { key: 'needs_response', name: '🤖 AI/Needs Response' },
    { key: 'outbox', name: '🤖 AI/Outbox' },
    { key: 'rework', name: '🤖 AI/Rework' },
    { key: 'action_required', name: '🤖 AI/Action Required' },
    { key: 'payment_request', name: '🤖 AI/Payment Requests' },
    { key: 'fyi', name: '🤖 AI/FYI' },
    { key: 'waiting', name: '🤖 AI/Waiting' },
    { key: 'done', name: '🤖 AI/Done' },
  ],
} as const;

/**
 * Provision all AI labels for a user
 * Creates parent label and 8 child labels
 * Returns mapping of label keys to Gmail label IDs
 */
export async function provisionAILabels(client: GmailClient): Promise<LabelMapping[]> {
  const mappings: LabelMapping[] = [];

  // Create parent label first
  const parentLabel = await client.createLabel(AI_LABELS.parent.name);
  if (!parentLabel.id) {
    throw new Error('Failed to create parent AI label');
  }

  mappings.push({
    key: AI_LABELS.parent.key,
    name: AI_LABELS.parent.name,
    gmailLabelId: parentLabel.id,
  });

  // Create child labels
  for (const childDef of AI_LABELS.children) {
    const label = await client.createLabel(childDef.name);
    if (!label.id) {
      throw new Error(`Failed to create label: ${childDef.name}`);
    }

    mappings.push({
      key: childDef.key,
      name: childDef.name,
      gmailLabelId: label.id,
    });
  }

  return mappings;
}

/**
 * Import existing labels from Gmail
 * Useful for migrating from v1 or recovering from database loss
 */
export async function importExistingLabels(client: GmailClient): Promise<LabelMapping[]> {
  const allLabels = await client.listLabels();
  const aiLabels = allLabels.filter((label) => label.name?.startsWith('🤖 AI'));

  const mappings: LabelMapping[] = [];

  // Map parent
  const parentLabel = aiLabels.find((l) => l.name === AI_LABELS.parent.name);
  if (parentLabel?.id) {
    mappings.push({
      key: AI_LABELS.parent.key,
      name: AI_LABELS.parent.name,
      gmailLabelId: parentLabel.id,
    });
  }

  // Map children
  for (const childDef of AI_LABELS.children) {
    const label = aiLabels.find((l) => l.name === childDef.name);
    if (label?.id) {
      mappings.push({
        key: childDef.key,
        name: childDef.name,
        gmailLabelId: label.id,
      });
    }
  }

  return mappings;
}

/**
 * Get label ID by key from mappings
 */
export function getLabelId(mappings: LabelMapping[], key: string): string | undefined {
  return mappings.find((m) => m.key === key)?.gmailLabelId;
}
