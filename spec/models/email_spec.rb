# frozen_string_literal: true

require "rails_helper"

RSpec.describe Email do
  describe "validations" do
    subject { build(:email) }

    it { is_expected.to validate_presence_of(:gmail_thread_id) }
    it { is_expected.to validate_uniqueness_of(:gmail_thread_id).scoped_to(:user_id) }
    it { is_expected.to validate_presence_of(:gmail_message_id) }
    it { is_expected.to validate_presence_of(:sender_email) }
    it { is_expected.to validate_inclusion_of(:classification).in_array(described_class::CLASSIFICATIONS) }
    it { is_expected.to validate_inclusion_of(:confidence).in_array(described_class::CONFIDENCES) }
    it { is_expected.to validate_inclusion_of(:status).in_array(described_class::STATUSES) }
    it { is_expected.to validate_numericality_of(:rework_count).is_greater_than_or_equal_to(0) }
    it { is_expected.to validate_numericality_of(:message_count).is_greater_than_or_equal_to(1) }
  end

  describe "associations" do
    it { is_expected.to belong_to(:user) }
  end

  describe "scopes" do
    let!(:user) { create(:user) }
    let!(:pending_email) { create(:email, user: user, status: "pending", classification: "needs_response") }
    let!(:drafted_email) { create(:email, :drafted, user: user) }
    let!(:fyi_email) { create(:email, :fyi, :archived, user: user) }

    it ".pending returns only pending emails" do
      expect(described_class.pending).to contain_exactly(pending_email)
    end

    it ".drafted returns only drafted emails" do
      expect(described_class.drafted).to contain_exactly(drafted_email)
    end

    it ".by_classification filters by classification" do
      expect(described_class.by_classification("fyi")).to contain_exactly(fyi_email)
    end

    it ".actionable returns needs_response, action_required, payment_request" do
      actionable = create(:email, :action_required, user: user)
      expect(described_class.actionable).to contain_exactly(pending_email, drafted_email, actionable)
    end
  end

  describe "#can_draft?" do
    it "returns true for pending needs_response emails" do
      email = build(:email, status: "pending", classification: "needs_response")
      expect(email.can_draft?).to be true
    end

    it "returns false for non-pending emails" do
      email = build(:email, :drafted, classification: "needs_response")
      expect(email.can_draft?).to be false
    end

    it "returns false for non-needs_response emails" do
      email = build(:email, status: "pending", classification: "fyi")
      expect(email.can_draft?).to be false
    end
  end

  describe "#mark_drafted!" do
    it "updates status and draft fields" do
      email = create(:email)
      email.mark_drafted!(draft_id: "draft_abc")

      expect(email.status).to eq("drafted")
      expect(email.draft_id).to eq("draft_abc")
      expect(email.drafted_at).to be_present
    end
  end

  describe "#request_rework!" do
    it "increments rework_count and updates status" do
      email = create(:email, :drafted)
      result = email.request_rework!(instruction: "Make it shorter")

      expect(result).to be true
      expect(email.status).to eq("rework_requested")
      expect(email.rework_count).to eq(1)
      expect(email.last_rework_instruction).to eq("Make it shorter")
    end

    it "returns false and marks skipped after 3 reworks" do
      email = create(:email, :drafted, rework_count: 3)
      result = email.request_rework!(instruction: "Fourth attempt")

      expect(result).to be false
      expect(email.status).to eq("skipped")
    end

    it "creates rework_limit_reached event when limit reached" do
      email = create(:email, :drafted, rework_count: 3)
      email.request_rework!(instruction: "Fourth attempt")

      event = EmailEvent.last
      expect(event.event_type).to eq("rework_limit_reached")
      expect(event.gmail_thread_id).to eq(email.gmail_thread_id)
    end
  end

  describe "#mark_sent!" do
    it "updates status and acted_at" do
      email = create(:email, :drafted)
      email.mark_sent!

      expect(email.status).to eq("sent")
      expect(email.acted_at).to be_present
    end
  end

  describe "#mark_archived!" do
    it "updates status and acted_at" do
      email = create(:email)
      email.mark_archived!

      expect(email.status).to eq("archived")
      expect(email.acted_at).to be_present
    end
  end

  describe "#rework_limit_reached?" do
    it "returns true when rework_count >= 3" do
      email = build(:email, rework_count: 3)
      expect(email.rework_limit_reached?).to be true
    end

    it "returns false when rework_count < 3" do
      email = build(:email, rework_count: 2)
      expect(email.rework_limit_reached?).to be false
    end
  end

  describe "#log_event" do
    it "creates an email event" do
      email = create(:email)
      email.log_event("classified", "Classified as needs_response")

      event = EmailEvent.last
      expect(event.user).to eq(email.user)
      expect(event.gmail_thread_id).to eq(email.gmail_thread_id)
      expect(event.event_type).to eq("classified")
      expect(event.detail).to eq("Classified as needs_response")
    end
  end
end
