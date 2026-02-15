# frozen_string_literal: true

FactoryBot.define do
  factory :email_event do
    user
    sequence(:gmail_thread_id) { |n| "thread_#{n}" }
    event_type { "classified" }
    detail { "Classified as needs_response" }

    EmailEvent::EVENT_TYPES.each do |type|
      trait type.to_sym do
        event_type { type }
      end
    end
  end
end
