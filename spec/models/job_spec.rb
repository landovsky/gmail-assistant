# frozen_string_literal: true

require "rails_helper"

RSpec.describe Job do
  describe "validations" do
    it { is_expected.to validate_presence_of(:job_type) }
    it { is_expected.to validate_inclusion_of(:job_type).in_array(described_class::JOB_TYPES) }
    it { is_expected.to validate_inclusion_of(:status).in_array(described_class::STATUSES) }
    it { is_expected.to validate_numericality_of(:attempts).is_greater_than_or_equal_to(0) }
    it { is_expected.to validate_numericality_of(:max_attempts).is_greater_than(0) }
  end

  describe "associations" do
    it { is_expected.to belong_to(:user) }
  end

  describe "scopes" do
    let!(:user) { create(:user) }
    let!(:pending_job) { create(:job, user: user, status: "pending") }
    let!(:running_job) { create(:job, :running, user: user) }
    let!(:completed_job) { create(:job, :completed, user: user) }

    it ".pending returns only pending jobs" do
      expect(described_class.pending).to contain_exactly(pending_job)
    end

    it ".running returns only running jobs" do
      expect(described_class.running).to contain_exactly(running_job)
    end

    it ".completed returns only completed jobs" do
      expect(described_class.completed).to contain_exactly(completed_job)
    end
  end

  describe "#claim!" do
    it "transitions pending to running" do
      job = create(:job)
      result = job.claim!

      expect(result).to be true
      expect(job.status).to eq("running")
      expect(job.started_at).to be_present
      expect(job.attempts).to eq(1)
    end

    it "returns false for non-pending jobs" do
      job = create(:job, :running)
      result = job.claim!

      expect(result).to be false
    end
  end

  describe "#complete!" do
    it "transitions to completed" do
      job = create(:job, :running)
      job.complete!

      expect(job.status).to eq("completed")
      expect(job.completed_at).to be_present
    end
  end

  describe "#fail!" do
    it "permanently fails after max attempts" do
      job = create(:job, :running, attempts: 3, max_attempts: 3)
      job.fail!("Something went wrong")

      expect(job.status).to eq("failed")
      expect(job.error_message).to eq("Something went wrong")
      expect(job.completed_at).to be_present
    end

    it "returns to pending if retries remain" do
      job = create(:job, :running, attempts: 1, max_attempts: 3)
      job.fail!("Temporary error")

      expect(job.status).to eq("pending")
      expect(job.error_message).to eq("Temporary error")
    end
  end

  describe ".enqueue" do
    it "creates a new pending job" do
      user = create(:user)
      job = described_class.enqueue(job_type: "classify", user: user)

      expect(job).to be_persisted
      expect(job.status).to eq("pending")
      expect(job.job_type).to eq("classify")
    end

    it "deduplicates identical pending jobs" do
      user = create(:user)
      job1 = described_class.enqueue(job_type: "classify", user: user)
      job2 = described_class.enqueue(job_type: "classify", user: user)

      expect(job1).to eq(job2)
      expect(described_class.where(user: user, job_type: "classify").count).to eq(1)
    end
  end

  describe ".claim_next" do
    it "claims the oldest pending job" do
      user = create(:user)
      old = create(:job, user: user, created_at: 2.minutes.ago)
      create(:job, user: user, created_at: 1.minute.ago)

      job = described_class.claim_next
      expect(job).to eq(old)
      expect(job.status).to eq("running")
    end

    it "filters by job_type when specified" do
      user = create(:user)
      create(:job, user: user, job_type: "classify")
      draft_job = create(:job, user: user, job_type: "draft")

      job = described_class.claim_next(job_type: "draft")
      expect(job).to eq(draft_job)
    end

    it "returns nil when no pending jobs exist" do
      expect(described_class.claim_next).to be_nil
    end
  end

  describe "#can_retry?" do
    it "returns true when attempts < max_attempts" do
      job = build(:job, attempts: 1, max_attempts: 3)
      expect(job.can_retry?).to be true
    end

    it "returns false when attempts >= max_attempts" do
      job = build(:job, attempts: 3, max_attempts: 3)
      expect(job.can_retry?).to be false
    end
  end

  describe "#parsed_payload" do
    it "parses JSON payload" do
      job = build(:job, payload: '{"thread_id": "abc"}')
      expect(job.parsed_payload).to eq({ "thread_id" => "abc" })
    end

    it "returns empty hash for invalid JSON" do
      job = build(:job, payload: "invalid")
      expect(job.parsed_payload).to eq({})
    end
  end
end
