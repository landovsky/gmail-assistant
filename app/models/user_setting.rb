# frozen_string_literal: true

class UserSetting < ApplicationRecord
  belongs_to :user

  STANDARD_KEYS = %w[
    communication_styles contacts sign_off_name default_language
  ].freeze

  validates :key, presence: true, uniqueness: { scope: :user_id }
  validates :value, presence: true

  def parsed_value
    JSON.parse(value)
  rescue JSON::ParserError
    value
  end

  def parsed_value=(new_value)
    self.value = new_value.is_a?(String) ? new_value : new_value.to_json
  end
end
