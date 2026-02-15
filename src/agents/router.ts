/**
 * Agent Routing System
 * Decides which emails go to standard pipeline vs agent processing
 */

/**
 * Email metadata for routing decisions
 */
export interface EmailMetadata {
  from: string;
  subject: string;
  headers: Record<string, string>;
  body: string;
}

/**
 * Routing rule match criteria
 */
export interface RoutingRuleMatch {
  all?: boolean;
  forwarded_from?: string;
  sender_domain?: string;
  sender_email?: string;
  subject_contains?: string;
  header_match?: Record<string, string>;
}

/**
 * Routing rule definition
 */
export interface RoutingRule {
  name: string;
  match: RoutingRuleMatch;
  route: "pipeline" | "agent";
  profile?: string; // Required if route = "agent"
}

/**
 * Routing decision result
 */
export interface RouteDecision {
  route: "pipeline" | "agent";
  profileName?: string;
  ruleName: string;
  metadata?: Record<string, any>;
}

/**
 * Agent Router
 * Evaluates emails against routing rules
 */
export class AgentRouter {
  private rules: RoutingRule[];

  constructor(rules: RoutingRule[]) {
    this.rules = rules;
    this.validateRules();
  }

  /**
   * Validate routing rules configuration
   */
  private validateRules(): void {
    for (const rule of this.rules) {
      if (rule.route === "agent" && !rule.profile) {
        throw new Error(
          `Rule "${rule.name}" has route=agent but no profile specified`
        );
      }
    }
  }

  /**
   * Evaluate email against all rules (first match wins)
   */
  route(email: EmailMetadata): RouteDecision {
    for (const rule of this.rules) {
      if (this.matchesRule(email, rule.match)) {
        return {
          route: rule.route,
          profileName: rule.profile,
          ruleName: rule.name,
          metadata: this.extractMetadata(email, rule.match),
        };
      }
    }

    // Default fallback to pipeline if no rules match
    return {
      route: "pipeline",
      ruleName: "default_fallback",
    };
  }

  /**
   * Check if email matches a rule's criteria
   * All specified criteria must match
   */
  private matchesRule(
    email: EmailMetadata,
    match: RoutingRuleMatch
  ): boolean {
    // Catch-all rule
    if (match.all === true) {
      return true;
    }

    // Check forwarded_from
    if (match.forwarded_from) {
      if (!this.isForwardedFrom(email, match.forwarded_from)) {
        return false;
      }
    }

    // Check sender_domain
    if (match.sender_domain) {
      const domain = this.extractDomain(email.from);
      if (domain?.toLowerCase() !== match.sender_domain.toLowerCase()) {
        return false;
      }
    }

    // Check sender_email
    if (match.sender_email) {
      if (email.from.toLowerCase() !== match.sender_email.toLowerCase()) {
        return false;
      }
    }

    // Check subject_contains
    if (match.subject_contains) {
      if (
        !email.subject
          .toLowerCase()
          .includes(match.subject_contains.toLowerCase())
      ) {
        return false;
      }
    }

    // Check header_match
    if (match.header_match) {
      for (const [headerName, headerValue] of Object.entries(
        match.header_match
      )) {
        const actualValue = email.headers[headerName];
        if (!actualValue || !new RegExp(headerValue).test(actualValue)) {
          return false;
        }
      }
    }

    // All criteria matched
    return true;
  }

  /**
   * Check if email is forwarded from a specific address
   * Checks multiple sources: sender, headers, body patterns
   */
  private isForwardedFrom(
    email: EmailMetadata,
    forwarderEmail: string
  ): boolean {
    const normalizedForwarder = forwarderEmail.toLowerCase();

    // Check sender email
    if (email.from.toLowerCase() === normalizedForwarder) {
      return true;
    }

    // Check X-Forwarded-From header
    const xForwardedFrom = email.headers["X-Forwarded-From"];
    if (xForwardedFrom?.toLowerCase().includes(normalizedForwarder)) {
      return true;
    }

    // Check Reply-To header
    const replyTo = email.headers["Reply-To"];
    if (replyTo?.toLowerCase().includes(normalizedForwarder)) {
      return true;
    }

    // Check body for forwarding patterns
    const forwardPatterns = [
      /From:\s*<?([^>\n]+)>?/i,
      /Od:\s*<?([^>\n]+)>?/i, // Czech
      /De:\s*<?([^>\n]+)>?/i, // Spanish/French
    ];

    for (const pattern of forwardPatterns) {
      const match = email.body.match(pattern);
      if (match && match[1]?.toLowerCase().includes(normalizedForwarder)) {
        return true;
      }
    }

    return false;
  }

  /**
   * Extract domain from email address
   */
  private extractDomain(email: string): string | null {
    const match = email.match(/@([^>]+)/);
    return match ? match[1].trim() : null;
  }

  /**
   * Extract metadata from email based on matched rule
   */
  private extractMetadata(
    email: EmailMetadata,
    match: RoutingRuleMatch
  ): Record<string, any> {
    const metadata: Record<string, any> = {};

    // Extract patient info if forwarded
    if (match.forwarded_from) {
      const patientInfo = this.extractPatientInfo(email);
      if (patientInfo) {
        metadata.patient = patientInfo;
      }
    }

    return metadata;
  }

  /**
   * Extract patient information from forwarded email
   * Used for preprocessing
   */
  private extractPatientInfo(email: EmailMetadata): {
    name?: string;
    email?: string;
  } | null {
    const info: { name?: string; email?: string } = {};

    // Extract name from body patterns
    const namePatterns = [
      /(From|Od|Name|Jméno):\s*(.+)/i,
      /Patient:\s*(.+)/i,
    ];

    for (const pattern of namePatterns) {
      const match = email.body.match(pattern);
      if (match && match[2]) {
        info.name = match[2].trim();
        break;
      }
    }

    // Extract email from Reply-To or body
    const replyTo = email.headers["Reply-To"];
    if (replyTo) {
      const emailMatch = replyTo.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
      if (emailMatch) {
        info.email = emailMatch[1];
      }
    }

    // Try body if no Reply-To
    if (!info.email) {
      const emailMatch = email.body.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
      if (emailMatch) {
        info.email = emailMatch[1];
      }
    }

    return info.name || info.email ? info : null;
  }

  /**
   * Get all configured rules
   */
  getRules(): RoutingRule[] {
    return this.rules;
  }
}
