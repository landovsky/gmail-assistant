# frozen_string_literal: true

require "rails_helper"

RSpec.describe Agent::Router do
  let(:rules) do
    [
      {
        "name" => "pharmacy_support",
        "match" => { "forwarded_from" => "info@pharmacy.cz" },
        "route" => "agent",
        "profile" => "pharmacy"
      },
      {
        "name" => "vip_client",
        "match" => { "sender_domain" => "important-client.com" },
        "route" => "agent",
        "profile" => "vip_handler"
      },
      {
        "name" => "urgent_emails",
        "match" => { "subject_contains" => "URGENT" },
        "route" => "agent",
        "profile" => "urgent_handler"
      },
      {
        "name" => "specific_sender",
        "match" => { "sender_email" => "ceo@company.com" },
        "route" => "agent",
        "profile" => "exec_handler"
      },
      {
        "name" => "default",
        "match" => { "all" => true },
        "route" => "pipeline"
      }
    ]
  end

  let(:router) { described_class.new(rules: rules) }

  describe "#route" do
    it "matches forwarded_from by sender email" do
      result = router.route(sender_email: "info@pharmacy.cz", subject: "Drug inquiry")
      expect(result.route).to eq("agent")
      expect(result.profile).to eq("pharmacy")
      expect(result.rule_name).to eq("pharmacy_support")
    end

    it "matches forwarded_from by X-Forwarded-From header" do
      result = router.route(
        sender_email: "forwarder@crisp.io",
        subject: "Forwarded message",
        headers: { "X-Forwarded-From" => "info@pharmacy.cz" }
      )
      expect(result.route).to eq("agent")
      expect(result.profile).to eq("pharmacy")
    end

    it "matches forwarded_from by Reply-To header" do
      result = router.route(
        sender_email: "forwarder@crisp.io",
        subject: "Forwarded message",
        headers: { "Reply-To" => "info@pharmacy.cz" }
      )
      expect(result.route).to eq("agent")
      expect(result.profile).to eq("pharmacy")
    end

    it "matches forwarded_from by body pattern" do
      result = router.route(
        sender_email: "forwarder@crisp.io",
        subject: "Forwarded message",
        body: "Some text\nFrom: Patient Name <info@pharmacy.cz>\nMessage body"
      )
      expect(result.route).to eq("agent")
      expect(result.profile).to eq("pharmacy")
    end

    it "matches sender_domain" do
      result = router.route(sender_email: "vip@important-client.com", subject: "Business")
      expect(result.route).to eq("agent")
      expect(result.profile).to eq("vip_handler")
    end

    it "matches sender_domain case-insensitively" do
      result = router.route(sender_email: "vip@Important-Client.COM", subject: "Business")
      expect(result.route).to eq("agent")
      expect(result.profile).to eq("vip_handler")
    end

    it "matches subject_contains" do
      result = router.route(sender_email: "someone@random.com", subject: "URGENT: Please respond")
      expect(result.route).to eq("agent")
      expect(result.profile).to eq("urgent_handler")
    end

    it "matches subject_contains case-insensitively" do
      result = router.route(sender_email: "someone@random.com", subject: "This is urgent!")
      expect(result.route).to eq("agent")
      expect(result.profile).to eq("urgent_handler")
    end

    it "matches sender_email exactly" do
      result = router.route(sender_email: "ceo@company.com", subject: "Hello")
      expect(result.route).to eq("agent")
      expect(result.profile).to eq("exec_handler")
    end

    it "falls through to catch-all default rule" do
      result = router.route(sender_email: "random@random.com", subject: "Hello")
      expect(result.route).to eq("pipeline")
      expect(result.profile).to be_nil
      expect(result.rule_name).to eq("default")
    end

    it "returns first matching rule (order matters)" do
      # This email matches both forwarded_from and sender_domain
      result = router.route(sender_email: "info@pharmacy.cz", subject: "URGENT drug query")
      expect(result.rule_name).to eq("pharmacy_support") # first rule wins
    end

    it "returns default_fallback when no rules match" do
      router_empty = described_class.new(rules: [])
      result = router_empty.route(sender_email: "test@test.com", subject: "Hello")
      expect(result.route).to eq("pipeline")
      expect(result.rule_name).to eq("default_fallback")
    end
  end
end
