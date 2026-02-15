# frozen_string_literal: true

class EmailEvent < ApplicationRecord
  belongs_to :user

  EVENT_TYPES = %w[
    classified label_added label_removed draft_created draft_trashed
    draft_reworked sent_detected archived rework_limit_reached
    waiting_retriaged error
  ].freeze

  validates :gmail_thread_id, presence: true
  validates :event_type, presence: true, inclusion: { in: EVENT_TYPES }

  # Append-only: prevent updates and deletes
  after_initialize :set_readonly, if: :persisted?

  scope :for_thread, ->(thread_id) { where(gmail_thread_id: thread_id) }
  scope :by_type, ->(type) { where(event_type: type) }
  scope :recent, -> { order(created_at: :desc) }
  scope :chronological, -> { order(created_at: :asc) }

  def email
    user.emails.find_by(gmail_thread_id: gmail_thread_id)
  end

  private

  def set_readonly
    # This makes the record read-only after it is persisted, enforcing append-only semantics
  end

  # Override to prevent updates on persisted records
  def readonly?
    persisted? && !new_record?
  end
end
