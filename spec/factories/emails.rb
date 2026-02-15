# frozen_string_literal: true

FactoryBot.define do
  factory :email do
    user
    sequence(:gmail_thread_id) { |n| "thread_#{n}" }
    sequence(:gmail_message_id) { |n| "msg_#{n}" }
    sender_email { "sender@example.com" }
    sender_name { "Test Sender" }
    subject { "Test Subject" }
    snippet { "This is a test email snippet..." }
    received_at { 1.hour.ago }
    classification { "needs_response" }
    confidence { "medium" }
    detected_language { "cs" }
    resolved_style { "business" }
    status { "pending" }

    trait :needs_response do
      classification { "needs_response" }
    end

    trait :action_required do
      classification { "action_required" }
    end

    trait :payment_request do
      classification { "payment_request" }
      vendor_name { "Test Vendor" }
    end

    trait :fyi do
      classification { "fyi" }
    end

    trait :waiting do
      classification { "waiting" }
    end

    trait :drafted do
      status { "drafted" }
      draft_id { "draft_123" }
      drafted_at { 30.minutes.ago }
    end

    trait :sent do
      status { "sent" }
      acted_at { 10.minutes.ago }
    end

    trait :rework_requested do
      status { "rework_requested" }
      last_rework_instruction { "Make it more formal" }
      rework_count { 1 }
    end

    trait :skipped do
      status { "skipped" }
    end

    trait :archived do
      status { "archived" }
      acted_at { 5.minutes.ago }
    end

    trait :high_confidence do
      confidence { "high" }
    end

    trait :low_confidence do
      confidence { "low" }
    end
  end
end
