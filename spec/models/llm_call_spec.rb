# frozen_string_literal: true

require "rails_helper"

RSpec.describe LlmCall do
  describe "validations" do
    it { is_expected.to validate_presence_of(:call_type) }
    it { is_expected.to validate_inclusion_of(:call_type).in_array(described_class::CALL_TYPES) }
    it { is_expected.to validate_presence_of(:model) }
  end

  describe "associations" do
    it { is_expected.to belong_to(:user).optional }
  end

  describe ".log_call" do
    it "creates an LLM call record with computed total_tokens" do
      user = create(:user)
      call = described_class.log_call(
        call_type: "classify",
        model: "gemini/gemini-2.0-flash",
        user: user,
        gmail_thread_id: "thread_1",
        prompt_tokens: 100,
        completion_tokens: 50,
        latency_ms: 250
      )

      expect(call).to be_persisted
      expect(call.total_tokens).to eq(150)
      expect(call.latency_ms).to eq(250)
    end
  end

  describe "#successful?" do
    it "returns true when no error" do
      call = build(:llm_call, error: nil)
      expect(call.successful?).to be true
    end

    it "returns false when error present" do
      call = build(:llm_call, :with_error)
      expect(call.successful?).to be false
    end
  end

  describe "scopes" do
    let!(:user) { create(:user) }

    it ".for_thread filters by thread ID" do
      call = create(:llm_call, user: user, gmail_thread_id: "t1")
      create(:llm_call, user: user, gmail_thread_id: "t2")

      expect(described_class.for_thread("t1")).to contain_exactly(call)
    end

    it ".with_errors returns only failed calls" do
      create(:llm_call, user: user)
      errored = create(:llm_call, :with_error, user: user)

      expect(described_class.with_errors).to contain_exactly(errored)
    end
  end
end
