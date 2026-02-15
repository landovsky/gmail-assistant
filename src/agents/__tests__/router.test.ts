/**
 * Agent Router Tests
 */

import { describe, test, expect } from "vitest";
import { AgentRouter } from "../router.js";
import type { RoutingRule, EmailMetadata } from "../router.js";

describe("AgentRouter", () => {
  describe("route decision", () => {
    test("should route to agent based on forwarded_from", () => {
      const rules: RoutingRule[] = [
        {
          name: "pharmacy_support",
          match: { forwarded_from: "info@pharmacy.com" },
          route: "agent",
          profile: "pharmacy",
        },
        {
          name: "default",
          match: { all: true },
          route: "pipeline",
        },
      ];

      const router = new AgentRouter(rules);

      const email: EmailMetadata = {
        from: "info@pharmacy.com",
        subject: "Drug availability question",
        headers: {},
        body: "Is Ibuprofen available?",
      };

      const decision = router.route(email);

      expect(decision.route).toBe("agent");
      expect(decision.profileName).toBe("pharmacy");
      expect(decision.ruleName).toBe("pharmacy_support");
    });

    test("should route to agent based on sender_domain", () => {
      const rules: RoutingRule[] = [
        {
          name: "vip_client",
          match: { sender_domain: "important-client.com" },
          route: "agent",
          profile: "vip_handler",
        },
        {
          name: "default",
          match: { all: true },
          route: "pipeline",
        },
      ];

      const router = new AgentRouter(rules);

      const email: EmailMetadata = {
        from: "boss@important-client.com",
        subject: "Project update",
        headers: {},
        body: "Need status update",
      };

      const decision = router.route(email);

      expect(decision.route).toBe("agent");
      expect(decision.profileName).toBe("vip_handler");
    });

    test("should route to agent based on subject_contains", () => {
      const rules: RoutingRule[] = [
        {
          name: "urgent_emails",
          match: { subject_contains: "URGENT" },
          route: "agent",
          profile: "urgent_handler",
        },
        {
          name: "default",
          match: { all: true },
          route: "pipeline",
        },
      ];

      const router = new AgentRouter(rules);

      const email: EmailMetadata = {
        from: "user@example.com",
        subject: "[URGENT] Server down",
        headers: {},
        body: "Please help!",
      };

      const decision = router.route(email);

      expect(decision.route).toBe("agent");
      expect(decision.profileName).toBe("urgent_handler");
    });

    test("should route to pipeline by default when no rules match", () => {
      const rules: RoutingRule[] = [
        {
          name: "specific_sender",
          match: { sender_email: "specific@example.com" },
          route: "agent",
          profile: "handler",
        },
      ];

      const router = new AgentRouter(rules);

      const email: EmailMetadata = {
        from: "other@example.com",
        subject: "Regular email",
        headers: {},
        body: "Hello",
      };

      const decision = router.route(email);

      expect(decision.route).toBe("pipeline");
      expect(decision.ruleName).toBe("default_fallback");
    });

    test("should use first matching rule", () => {
      const rules: RoutingRule[] = [
        {
          name: "rule1",
          match: { sender_domain: "example.com" },
          route: "agent",
          profile: "profile1",
        },
        {
          name: "rule2",
          match: { sender_domain: "example.com" },
          route: "agent",
          profile: "profile2",
        },
        {
          name: "default",
          match: { all: true },
          route: "pipeline",
        },
      ];

      const router = new AgentRouter(rules);

      const email: EmailMetadata = {
        from: "user@example.com",
        subject: "Test",
        headers: {},
        body: "Test",
      };

      const decision = router.route(email);

      expect(decision.ruleName).toBe("rule1");
      expect(decision.profileName).toBe("profile1");
    });

    test("should match all criteria when multiple specified", () => {
      const rules: RoutingRule[] = [
        {
          name: "compound_rule",
          match: {
            sender_domain: "client.com",
            subject_contains: "urgent",
          },
          route: "agent",
          profile: "urgent_client",
        },
        {
          name: "default",
          match: { all: true },
          route: "pipeline",
        },
      ];

      const router = new AgentRouter(rules);

      // Matches both criteria
      const match1 = router.route({
        from: "user@client.com",
        subject: "URGENT request",
        headers: {},
        body: "Help",
      });

      expect(match1.route).toBe("agent");
      expect(match1.ruleName).toBe("compound_rule");

      // Matches only one criterion
      const match2 = router.route({
        from: "user@other.com",
        subject: "URGENT request",
        headers: {},
        body: "Help",
      });

      expect(match2.route).toBe("pipeline");
      expect(match2.ruleName).toBe("default");
    });
  });

  describe("forwarded_from detection", () => {
    test("should detect forwarded email from sender", () => {
      const rules: RoutingRule[] = [
        {
          name: "forwarded",
          match: { forwarded_from: "helpdesk@support.com" },
          route: "agent",
          profile: "support",
        },
      ];

      const router = new AgentRouter(rules);

      const email: EmailMetadata = {
        from: "helpdesk@support.com",
        subject: "Fwd: Customer question",
        headers: {},
        body: "Customer asks about product",
      };

      const decision = router.route(email);

      expect(decision.route).toBe("agent");
    });

    test("should detect forwarded email from X-Forwarded-From header", () => {
      const rules: RoutingRule[] = [
        {
          name: "forwarded",
          match: { forwarded_from: "system@helpdesk.com" },
          route: "agent",
          profile: "support",
        },
      ];

      const router = new AgentRouter(rules);

      const email: EmailMetadata = {
        from: "user@example.com",
        subject: "Question",
        headers: {
          "X-Forwarded-From": "system@helpdesk.com",
        },
        body: "Question text",
      };

      const decision = router.route(email);

      expect(decision.route).toBe("agent");
    });

    test("should detect forwarded email from body pattern", () => {
      const rules: RoutingRule[] = [
        {
          name: "forwarded",
          match: { forwarded_from: "patient@email.com" },
          route: "agent",
          profile: "pharmacy",
        },
      ];

      const router = new AgentRouter(rules);

      const email: EmailMetadata = {
        from: "crisp@helpdesk.com",
        subject: "Fwd: Question",
        headers: {},
        body: "From: patient@email.com\n\nMy question is...",
      };

      const decision = router.route(email);

      expect(decision.route).toBe("agent");
    });
  });

  describe("patient info extraction", () => {
    test("should extract patient name and email from forwarded message", () => {
      const rules: RoutingRule[] = [
        {
          name: "pharmacy",
          match: { forwarded_from: "info@crisp.com" },
          route: "agent",
          profile: "pharmacy",
        },
      ];

      const router = new AgentRouter(rules);

      const email: EmailMetadata = {
        from: "info@crisp.com",
        subject: "Fwd: Drug question",
        headers: {
          "Reply-To": "patient@example.com",
        },
        body: "From: Jan Novák\n\nIs Aspirin available?",
      };

      const decision = router.route(email);

      expect(decision.metadata?.patient).toBeDefined();
      expect(decision.metadata?.patient.name).toBe("Jan Novák");
      expect(decision.metadata?.patient.email).toBe("patient@example.com");
    });
  });

  describe("validation", () => {
    test("should throw error if agent route has no profile", () => {
      const rules: RoutingRule[] = [
        {
          name: "broken_rule",
          match: { all: true },
          route: "agent",
          // Missing profile!
        } as RoutingRule,
      ];

      expect(() => new AgentRouter(rules)).toThrow();
    });
  });
});
