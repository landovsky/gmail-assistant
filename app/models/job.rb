# frozen_string_literal: true

class Job < ApplicationRecord
  belongs_to :user

  JOB_TYPES = %w[sync classify draft cleanup rework manual_draft agent_process].freeze
  STATUSES = %w[pending running completed failed].freeze

  validates :job_type, presence: true, inclusion: { in: JOB_TYPES }
  validates :status, inclusion: { in: STATUSES }
  validates :attempts, numericality: { greater_than_or_equal_to: 0 }
  validates :max_attempts, numericality: { greater_than: 0 }

  scope :pending, -> { where(status: "pending") }
  scope :running, -> { where(status: "running") }
  scope :completed, -> { where(status: "completed") }
  scope :failed, -> { where(status: "failed") }
  scope :claimable, -> { pending.order(created_at: :asc) }
  scope :by_type, ->(type) { where(job_type: type) }
  scope :stale, -> { where(status: %w[completed failed]).where(created_at: ...7.days.ago) }

  def claim!
    return false unless status == "pending"

    update!(
      status: "running",
      started_at: Time.current,
      attempts: attempts + 1
    )
    true
  end

  def complete!
    update!(
      status: "completed",
      completed_at: Time.current
    )
  end

  def fail!(error_msg)
    if attempts >= max_attempts
      update!(
        status: "failed",
        error_message: error_msg,
        completed_at: Time.current
      )
    else
      update!(
        status: "pending",
        error_message: error_msg
      )
    end
  end

  def parsed_payload
    JSON.parse(payload)
  rescue JSON::ParserError
    {}
  end

  def can_retry?
    attempts < max_attempts
  end

  def self.enqueue(job_type:, user:, payload: {})
    # Deduplication: don't enqueue if identical pending job exists
    existing = pending.find_by(job_type: job_type, user: user, payload: payload.to_json)
    return existing if existing

    create!(
      job_type: job_type,
      user: user,
      payload: payload.to_json
    )
  end

  def self.claim_next(job_type: nil)
    scope = claimable
    scope = scope.by_type(job_type) if job_type
    job = scope.lock.first
    return nil unless job

    job.claim!
    job
  end
end
