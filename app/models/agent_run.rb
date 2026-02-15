# frozen_string_literal: true

class AgentRun < ApplicationRecord
  belongs_to :user

  STATUSES = %w[running completed error max_iterations].freeze

  validates :gmail_thread_id, presence: true
  validates :profile, presence: true
  validates :status, inclusion: { in: STATUSES }
  validates :iterations, numericality: { greater_than_or_equal_to: 0 }

  scope :running, -> { where(status: "running") }
  scope :completed, -> { where(status: "completed") }
  scope :errored, -> { where(status: "error") }
  scope :for_thread, ->(thread_id) { where(gmail_thread_id: thread_id) }
  scope :by_profile, ->(profile) { where(profile: profile) }
  scope :recent, -> { order(created_at: :desc) }

  def parsed_tool_calls
    JSON.parse(tool_calls_log)
  rescue JSON::ParserError
    []
  end

  def log_tool_call(tool_name:, input:, output:)
    calls = parsed_tool_calls
    calls << {
      tool: tool_name,
      input: input,
      output: output,
      timestamp: Time.current.iso8601
    }
    update!(tool_calls_log: calls.to_json, iterations: iterations + 1)
  end

  def complete!(message)
    update!(
      status: "completed",
      final_message: message,
      completed_at: Time.current
    )
  end

  def fail!(error_msg)
    update!(
      status: "error",
      error: error_msg,
      completed_at: Time.current
    )
  end

  def max_iterations!(message = nil)
    update!(
      status: "max_iterations",
      final_message: message,
      completed_at: Time.current
    )
  end
end
