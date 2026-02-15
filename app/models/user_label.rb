# frozen_string_literal: true

class UserLabel < ApplicationRecord
  belongs_to :user

  STANDARD_KEYS = %w[
    needs_response action_required payment_request fyi waiting
    outbox rework done
  ].freeze

  validates :label_key, presence: true, uniqueness: { scope: :user_id }
  validates :gmail_label_id, presence: true
  validates :gmail_label_name, presence: true

  scope :for_key, ->(key) { where(label_key: key) }
  scope :classification_labels, -> { where(label_key: %w[needs_response action_required payment_request fyi waiting]) }
  scope :workflow_labels, -> { where(label_key: %w[outbox rework done]) }
end
