# frozen_string_literal: true

class User < ApplicationRecord
  has_many :emails, dependent: :destroy
  has_many :user_labels, dependent: :destroy
  has_many :user_settings, dependent: :destroy
  has_one :sync_state, dependent: :destroy
  has_many :jobs, dependent: :destroy
  has_many :email_events, dependent: :destroy
  has_many :llm_calls, dependent: :nullify
  has_many :agent_runs, dependent: :destroy

  validates :email, presence: true, uniqueness: true,
                    format: { with: URI::MailTo::EMAIL_REGEXP, message: "must be a valid email address" }

  after_create :create_sync_state!

  scope :active, -> { where(is_active: true) }
  scope :onboarded, -> { where.not(onboarded_at: nil) }

  def onboarded?
    onboarded_at.present?
  end

  def label_for(key)
    user_labels.find_by(label_key: key)
  end

  def setting_for(key)
    setting = user_settings.find_by(key: key)
    return nil unless setting

    JSON.parse(setting.value)
  rescue JSON::ParserError
    setting.value
  end

  def update_setting(key, value)
    json_value = value.is_a?(String) ? value : value.to_json
    setting = user_settings.find_or_initialize_by(key: key)
    setting.update!(value: json_value)
    setting
  end

  private

  def create_sync_state!
    SyncState.create!(user: self)
  end
end
