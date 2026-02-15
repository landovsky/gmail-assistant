/**
 * Pharmacy Agent Tools
 * Domain-specific tools for pharmacy email handling.
 *
 * These tools provide drug search, reservation management, and web search
 * capabilities. They return structured mock data since no external pharmacy
 * API is currently integrated. Replace the inner logic when a real
 * pharmacy backend becomes available.
 */

import { z } from 'zod';
import { toolRegistry, type ToolDefinition, type ToolContext } from './registry.js';

// ---------------------------------------------------------------------------
// search_drugs
// ---------------------------------------------------------------------------

const searchDrugsSchema = z.object({
  drug_name: z.string().describe('Name of the drug to search for'),
});

const searchDrugsDefinition: ToolDefinition = {
  type: 'function',
  function: {
    name: 'search_drugs',
    description:
      'Search for drug availability in the pharmacy database. Returns availability status and pricing information.',
    parameters: {
      type: 'object',
      properties: {
        drug_name: {
          type: 'string',
          description: 'Name of the drug to search for',
        },
      },
      required: ['drug_name'],
    },
  },
};

async function searchDrugsHandler({
  args,
}: {
  userId: number;
  args: z.infer<typeof searchDrugsSchema>;
  context?: ToolContext;
}): Promise<string> {
  const { drug_name } = args;

  // Mock data -- replace with real pharmacy API integration
  const normalizedName = drug_name.toLowerCase().trim();

  // Simulate a few known drugs for realistic agent behavior
  const mockDatabase: Record<
    string,
    { available: boolean; price?: string; alternatives?: string[] }
  > = {
    'ibuprofen 400mg': {
      available: true,
      price: '89 CZK',
    },
    ibuprofen: {
      available: true,
      price: '89 CZK (400mg), 59 CZK (200mg)',
    },
    paracetamol: {
      available: true,
      price: '49 CZK',
    },
    amoxicillin: {
      available: false,
      alternatives: ['Augmentin', 'Cefuroxim'],
    },
  };

  // Find a matching entry (partial match)
  let result = mockDatabase[normalizedName];
  if (!result) {
    for (const [key, value] of Object.entries(mockDatabase)) {
      if (normalizedName.includes(key) || key.includes(normalizedName)) {
        result = value;
        break;
      }
    }
  }

  if (!result) {
    return `Drug "${drug_name}" not found in database. Please verify the drug name and try again, or escalate to a pharmacist.`;
  }

  if (result.available) {
    return `Drug "${drug_name}" is available. Price: ${result.price}. Ready for pickup or reservation.`;
  }

  const altText = result.alternatives?.length
    ? ` Possible alternatives: ${result.alternatives.join(', ')}.`
    : '';
  return `Drug "${drug_name}" is currently not available.${altText} Consider suggesting an alternative or escalating.`;
}

// ---------------------------------------------------------------------------
// manage_reservation
// ---------------------------------------------------------------------------

const manageReservationSchema = z.object({
  action: z.enum(['create', 'check', 'cancel']).describe('Reservation action to perform'),
  drug_name: z.string().describe('Name of the drug'),
  patient_name: z.string().describe('Name of the patient'),
  patient_email: z.string().describe('Email address of the patient'),
});

const manageReservationDefinition: ToolDefinition = {
  type: 'function',
  function: {
    name: 'manage_reservation',
    description:
      "Create, check, or cancel a drug reservation for a patient. Use 'create' to reserve a drug, 'check' to look up existing reservations, or 'cancel' to cancel one.",
    parameters: {
      type: 'object',
      properties: {
        action: {
          type: 'string',
          enum: ['create', 'check', 'cancel'],
          description: 'Reservation action to perform',
        },
        drug_name: {
          type: 'string',
          description: 'Name of the drug',
        },
        patient_name: {
          type: 'string',
          description: 'Name of the patient',
        },
        patient_email: {
          type: 'string',
          description: 'Email address of the patient',
        },
      },
      required: ['action', 'drug_name', 'patient_name', 'patient_email'],
    },
  },
};

async function manageReservationHandler({
  args,
}: {
  userId: number;
  args: z.infer<typeof manageReservationSchema>;
  context?: ToolContext;
}): Promise<string> {
  const { action, drug_name, patient_name, patient_email } = args;

  // Mock implementation -- replace with real reservation system
  const reservationId = `RES-${Date.now().toString(36).toUpperCase()}`;

  switch (action) {
    case 'create':
      return (
        `Reservation created successfully.\n` +
        `Reservation ID: ${reservationId}\n` +
        `Drug: ${drug_name}\n` +
        `Patient: ${patient_name} (${patient_email})\n` +
        `Pickup deadline: 3 business days\n` +
        `Please inform the patient of their reservation ID.`
      );

    case 'check':
      return (
        `No active reservations found for patient ${patient_name} (${patient_email}) ` +
        `for drug "${drug_name}". You may create a new reservation if needed.`
      );

    case 'cancel':
      return (
        `No active reservation found for patient ${patient_name} (${patient_email}) ` +
        `for drug "${drug_name}" to cancel.`
      );

    default:
      return `Unknown reservation action: ${action}`;
  }
}

// ---------------------------------------------------------------------------
// web_search
// ---------------------------------------------------------------------------

const webSearchSchema = z.object({
  query: z.string().describe('Search query for drug information'),
});

const webSearchDefinition: ToolDefinition = {
  type: 'function',
  function: {
    name: 'web_search',
    description:
      "Search the web for drug information, side effects, interactions, or dosage guidelines. Use when the pharmacy database doesn't have enough information.",
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query for drug information',
        },
      },
      required: ['query'],
    },
  },
};

async function webSearchHandler({
  args,
}: {
  userId: number;
  args: z.infer<typeof webSearchSchema>;
  context?: ToolContext;
}): Promise<string> {
  const { query } = args;

  // Mock implementation -- replace with real search API (e.g., Tavily, Serper)
  return (
    `Web search results for "${query}":\n\n` +
    `Note: Web search integration is not yet configured. ` +
    `For medical information, please recommend the patient consult their doctor or pharmacist directly. ` +
    `If you need specific drug interaction or dosage information, consider escalating to a human pharmacist.`
  );
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

export function registerPharmacyTools(): void {
  toolRegistry.register(searchDrugsDefinition, searchDrugsSchema, searchDrugsHandler);
  toolRegistry.register(
    manageReservationDefinition,
    manageReservationSchema,
    manageReservationHandler
  );
  toolRegistry.register(webSearchDefinition, webSearchSchema, webSearchHandler);
}
