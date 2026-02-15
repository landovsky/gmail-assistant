# frozen_string_literal: true

class LlmCall < ApplicationRecord
  belongs_to :user, optional: true

  CALL_TYPES = %w[classify draft rework context agent].freeze

  validates :call_type, presence: true, inclusion: { in: CALL_TYPES }
  validates :model, presence: true

  scope :for_thread, ->(thread_id) { where(gmail_thread_id: thread_id) }
  scope :by_type, ->(type) { where(call_type: type) }
  scope :recent, -> { order(created_at: :desc) }
  scope :with_errors, -> { where.not(error: nil) }
  scope :successful, -> { where(error: nil) }

  def total_cost_estimate
    # Rough cost estimation based on tokens - can be overridden with actual pricing
    total_tokens * 0.00001
  end

  def duration_seconds
    latency_ms / 1000.0
  end

  def successful?
    error.blank?
  end

  def self.log_call(call_type:, model:, user: nil, gmail_thread_id: nil,
                    system_prompt: nil, user_message: nil, response_text: nil,
                    prompt_tokens: 0, completion_tokens: 0, latency_ms: 0, error: nil)
    create!(
      user: user,
      gmail_thread_id: gmail_thread_id,
      call_type: call_type,
      model: model,
      system_prompt: system_prompt,
      user_message: user_message,
      response_text: response_text,
      prompt_tokens: prompt_tokens,
      completion_tokens: completion_tokens,
      total_tokens: prompt_tokens + completion_tokens,
      latency_ms: latency_ms,
      error: error
    )
  end
end
