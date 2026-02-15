# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Email Lifecycle State Machine", type: :integration do
  let(:user) { create(:user) }

  before do
    %w[needs_response action_required payment_request fyi waiting outbox rework done].each_with_index do |key, i|
      create(:user_label, user: user, label_key: key, gmail_label_id: "Label_#{i}")
    end
  end

  describe "pending -> drafted -> sent lifecycle" do
    it "transitions through the complete needs_response lifecycle" do
      # Step 1: Create email in pending state
      email = create(:email, user: user, classification: "needs_response", status: "pending")
      expect(email.can_draft?).to be true

      # Step 2: Mark as drafted
      email.mark_drafted!(draft_id: "draft_123")
      expect(email.status).to eq("drafted")
      expect(email.draft_id).to eq("draft_123")
      expect(email.drafted_at).to be_present

      # Step 3: Mark as sent
      email.mark_sent!
      expect(email.status).to eq("sent")
      expect(email.acted_at).to be_present

      # Step 4: Archive
      email.mark_archived!
      expect(email.status).to eq("archived")
    end
  end

  describe "drafted -> rework_requested -> drafted cycle" do
    it "supports up to 3 rework iterations" do
      email = create(:email, user: user, classification: "needs_response", status: "drafted",
                     draft_id: "draft_1", drafted_at: Time.current)

      # Rework 1
      result = email.request_rework!(instruction: "Make it shorter")
      expect(result).to be true
      expect(email.status).to eq("rework_requested")
      expect(email.rework_count).to eq(1)
      expect(email.last_rework_instruction).to eq("Make it shorter")

      # Simulate re-draft
      email.update!(status: "drafted", draft_id: "draft_2", drafted_at: Time.current)

      # Rework 2
      result = email.request_rework!(instruction: "More formal")
      expect(result).to be true
      expect(email.rework_count).to eq(2)
      email.update!(status: "drafted", draft_id: "draft_3")

      # Rework 3
      result = email.request_rework!(instruction: "Add more detail")
      expect(result).to be true
      expect(email.rework_count).to eq(3)
      email.update!(status: "drafted", draft_id: "draft_4")

      # Rework 4 - should hit limit
      result = email.request_rework!(instruction: "One more change")
      expect(result).to be false
      expect(email.status).to eq("skipped")

      # Event logged
      events = EmailEvent.where(gmail_thread_id: email.gmail_thread_id)
      expect(events.map(&:event_type)).to include("rework_limit_reached")
    end
  end

  describe "fyi/action_required -> skipped flow" do
    it "does not generate drafts for non-response classifications" do
      email = create(:email, user: user, classification: "fyi", status: "pending")
      expect(email.can_draft?).to be false

      email2 = create(:email, user: user, classification: "action_required", status: "pending",
                       gmail_thread_id: "thread_ar_1", gmail_message_id: "msg_ar_1")
      expect(email2.can_draft?).to be false

      email3 = create(:email, user: user, classification: "payment_request", status: "pending",
                       gmail_thread_id: "thread_pr_1", gmail_message_id: "msg_pr_1")
      expect(email3.can_draft?).to be false
    end
  end

  describe "user marks Done" do
    it "archives email from any status" do
      %w[drafted sent skipped].each do |initial_status|
        email = create(:email,
                       user: user,
                       status: initial_status,
                       gmail_thread_id: "thread_done_#{initial_status}",
                       gmail_message_id: "msg_done_#{initial_status}")

        email.mark_archived!
        expect(email.status).to eq("archived")
        expect(email.acted_at).to be_present
      end
    end
  end

  describe "event audit trail" do
    it "creates events for each state transition" do
      email = create(:email, user: user, classification: "needs_response", status: "pending")

      # Log classification
      email.log_event("classified", "Classified as needs_response")

      # Mark drafted
      email.mark_drafted!(draft_id: "draft_1")
      email.log_event("draft_created", "Draft generated", draft_id: "draft_1")

      # Mark sent
      email.mark_sent!
      email.log_event("sent_detected", "Draft was sent")

      # Archive
      email.mark_archived!
      email.log_event("archived", "User marked as done")

      events = EmailEvent.where(gmail_thread_id: email.gmail_thread_id).order(:created_at)
      event_types = events.pluck(:event_type)

      expect(event_types).to eq(%w[classified draft_created sent_detected archived])
      expect(events.all? { |e| e.user_id == user.id }).to be true
    end
  end

  describe "state invariants" do
    it "enforces valid status values" do
      email = build(:email, user: user, status: "invalid_status")
      expect(email).not_to be_valid
      expect(email.errors[:status]).to be_present
    end

    it "enforces valid classification values" do
      email = build(:email, user: user, classification: "invalid_class")
      expect(email).not_to be_valid
      expect(email.errors[:classification]).to be_present
    end

    it "enforces unique thread per user" do
      create(:email, user: user, gmail_thread_id: "thread_unique_1")
      duplicate = build(:email, user: user, gmail_thread_id: "thread_unique_1",
                        gmail_message_id: "msg_unique_2")
      expect(duplicate).not_to be_valid
    end

    it "enforces rework_count >= 0" do
      email = build(:email, user: user, rework_count: -1)
      expect(email).not_to be_valid
    end
  end
end
