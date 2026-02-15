# frozen_string_literal: true

FactoryBot.define do
  factory :agent_run do
    user
    gmail_thread_id { "thread_1" }
    profile { "pharmacy_support" }
    status { "running" }
    tool_calls_log { "[]" }
    iterations { 0 }

    trait :completed do
      status { "completed" }
      final_message { "Email processed successfully" }
      completed_at { 1.minute.ago }
    end

    trait :errored do
      status { "error" }
      error { "Tool execution failed" }
      completed_at { 1.minute.ago }
    end

    trait :max_iterations do
      status { "max_iterations" }
      iterations { 10 }
      completed_at { 1.minute.ago }
    end
  end
end
