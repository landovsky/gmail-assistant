# frozen_string_literal: true

class Email < ApplicationRecord
  belongs_to :user
  has_many :email_events, ->(email) { where(gmail_thread_id: email.gmail_thread_id) },
           through: :user, source: :email_events
  has_many :llm_calls, ->(email) { where(gmail_thread_id: email.gmail_thread_id) },
           through: :user, source: :llm_calls

  CLASSIFICATIONS = %w[needs_response action_required payment_request fyi waiting].freeze
  CONFIDENCES = %w[high medium low].freeze
  STATUSES = %w[pending drafted rework_requested sent skipped archived].freeze

  validates :gmail_thread_id, presence: true, uniqueness: { scope: :user_id }
  validates :gmail_message_id, presence: true
  validates :sender_email, presence: true
  validates :classification, inclusion: { in: CLASSIFICATIONS }, allow_nil: false
  validates :confidence, inclusion: { in: CONFIDENCES }, allow_nil: false
  validates :status, inclusion: { in: STATUSES }, allow_nil: false
  validates :rework_count, numericality: { greater_than_or_equal_to: 0 }
  validates :message_count, numericality: { greater_than_or_equal_to: 1 }

  scope :by_classification, ->(classification) { where(classification: classification) }
  scope :by_status, ->(status) { where(status: status) }
  scope :pending, -> { where(status: "pending") }
  scope :drafted, -> { where(status: "drafted") }
  scope :needs_response, -> { where(classification: "needs_response") }
  scope :actionable, -> { where(classification: %w[needs_response action_required payment_request]) }
  scope :recent, -> { order(received_at: :desc) }

  # State machine transitions
  def can_draft?
    status == "pending" && classification == "needs_response"
  end

  def mark_drafted!(draft_id:)
    update!(
      status: "drafted",
      draft_id: draft_id,
      drafted_at: Time.current
    )
  end

  def request_rework!(instruction:)
    if rework_count >= 3
      update!(status: "skipped")
      log_event("rework_limit_reached", "Rework limit of 3 reached")
      return false
    end

    update!(
      status: "rework_requested",
      last_rework_instruction: instruction,
      rework_count: rework_count + 1
    )
    true
  end

  def mark_sent!
    update!(
      status: "sent",
      acted_at: Time.current
    )
  end

  def mark_archived!
    update!(
      status: "archived",
      acted_at: Time.current
    )
  end

  def mark_skipped!
    update!(status: "skipped")
  end

  def rework_limit_reached?
    rework_count >= 3
  end

  def log_event(event_type, detail = nil, label_id: nil, draft_id: nil)
    EmailEvent.create!(
      user: user,
      gmail_thread_id: gmail_thread_id,
      event_type: event_type,
      detail: detail,
      label_id: label_id,
      draft_id: draft_id
    )
  end
end
