# frozen_string_literal: true

require "rails_helper"

RSpec.describe Classification::RuleEngine do
  describe "#evaluate" do
    context "without user (no blacklist)" do
      let(:engine) { described_class.new }

      it "detects noreply sender" do
        result = engine.evaluate(sender_email: "noreply@company.com")
        expect(result[:is_automated]).to be true
        expect(result[:rule_name]).to eq("automated_sender")
      end

      it "detects no-reply sender" do
        result = engine.evaluate(sender_email: "no-reply@example.com")
        expect(result[:is_automated]).to be true
      end

      it "detects notifications sender" do
        result = engine.evaluate(sender_email: "notifications@github.com")
        expect(result[:is_automated]).to be true
      end

      it "detects mailer-daemon sender" do
        result = engine.evaluate(sender_email: "mailer-daemon@mail.com")
        expect(result[:is_automated]).to be true
      end

      it "passes normal sender" do
        result = engine.evaluate(sender_email: "john.doe@company.com")
        expect(result[:is_automated]).to be false
      end

      it "detects Auto-Submitted header" do
        result = engine.evaluate(
          sender_email: "person@example.com",
          headers: { "Auto-Submitted" => "auto-generated" }
        )
        expect(result[:is_automated]).to be true
        expect(result[:rule_name]).to eq("rfc_header")
      end

      it "detects Precedence: bulk header" do
        result = engine.evaluate(
          sender_email: "person@example.com",
          headers: { "Precedence" => "bulk" }
        )
        expect(result[:is_automated]).to be true
      end

      it "detects List-Unsubscribe header" do
        result = engine.evaluate(
          sender_email: "newsletter@example.com",
          headers: { "List-Unsubscribe" => "<https://example.com/unsub>" }
        )
        expect(result[:is_automated]).to be true
      end

      it "detects List-Id header" do
        result = engine.evaluate(
          sender_email: "list@example.com",
          headers: { "List-Id" => "mylist.example.com" }
        )
        expect(result[:is_automated]).to be true
      end
    end

    context "with user blacklist" do
      let(:user) { create(:user) }

      before do
        user.update_setting("contacts", {
          "blacklist" => ["noreply@*.com", "*-noreply@*", "spam@specific.com"]
        })
      end

      let(:engine) { described_class.new(user: user) }

      it "matches glob blacklist patterns" do
        result = engine.evaluate(sender_email: "noreply@anything.com")
        expect(result[:is_automated]).to be true
        expect(result[:rule_name]).to eq("blacklist_match")
      end

      it "matches wildcard blacklist patterns" do
        result = engine.evaluate(sender_email: "sales-noreply@company.org")
        expect(result[:is_automated]).to be true
        expect(result[:rule_name]).to eq("blacklist_match")
      end

      it "matches exact blacklist entries" do
        result = engine.evaluate(sender_email: "spam@specific.com")
        expect(result[:is_automated]).to be true
      end

      it "does not match non-blacklisted senders" do
        result = engine.evaluate(sender_email: "colleague@company.com")
        expect(result[:is_automated]).to be false
      end
    end
  end
end
