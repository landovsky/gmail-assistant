# frozen_string_literal: true

class SyncState < ApplicationRecord
  belongs_to :user

  validates :user_id, uniqueness: true
  validates :last_history_id, presence: true

  def watch_active?
    watch_expiration.present? && watch_expiration > Time.current
  end

  def needs_full_sync?
    last_history_id == "0"
  end

  def update_history_id!(history_id)
    update!(
      last_history_id: history_id,
      last_sync_at: Time.current
    )
  end

  def update_watch!(expiration:, resource_id:)
    update!(
      watch_expiration: expiration,
      watch_resource_id: resource_id
    )
  end
end
