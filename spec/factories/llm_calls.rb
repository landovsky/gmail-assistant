# frozen_string_literal: true

FactoryBot.define do
  factory :llm_call do
    user
    gmail_thread_id { "thread_1" }
    call_type { "classify" }
    model { "gemini/gemini-2.0-flash" }
    system_prompt { "You are a classifier." }
    user_message { "Classify this email." }
    response_text { '{"category": "needs_response"}' }
    prompt_tokens { 100 }
    completion_tokens { 50 }
    total_tokens { 150 }
    latency_ms { 500 }

    trait :draft do
      call_type { "draft" }
      model { "gemini/gemini-2.5-pro" }
    end

    trait :rework do
      call_type { "rework" }
    end

    trait :with_error do
      response_text { nil }
      error { "API rate limit exceeded" }
    end
  end
end
