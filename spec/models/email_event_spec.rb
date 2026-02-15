# frozen_string_literal: true

require "rails_helper"

RSpec.describe EmailEvent do
  describe "validations" do
    it { is_expected.to validate_presence_of(:gmail_thread_id) }
    it { is_expected.to validate_presence_of(:event_type) }
    it { is_expected.to validate_inclusion_of(:event_type).in_array(described_class::EVENT_TYPES) }
  end

  describe "associations" do
    it { is_expected.to belong_to(:user) }
  end

  describe "append-only semantics" do
    it "prevents updates on persisted records" do
      event = create(:email_event)
      expect { event.update!(detail: "changed") }.to raise_error(ActiveRecord::ReadOnlyRecord)
    end
  end

  describe "scopes" do
    let!(:user) { create(:user) }

    it ".for_thread returns events for a specific thread" do
      event = create(:email_event, user: user, gmail_thread_id: "thread_1")
      create(:email_event, user: user, gmail_thread_id: "thread_2")

      expect(described_class.for_thread("thread_1")).to contain_exactly(event)
    end

    it ".by_type filters by event type" do
      classified = create(:email_event, user: user, event_type: "classified")
      create(:email_event, user: user, event_type: "sent_detected")

      expect(described_class.by_type("classified")).to contain_exactly(classified)
    end
  end

  describe "#email" do
    it "returns the associated email record" do
      user = create(:user)
      email = create(:email, user: user, gmail_thread_id: "thread_x")
      event = create(:email_event, user: user, gmail_thread_id: "thread_x")

      expect(event.email).to eq(email)
    end
  end
end
