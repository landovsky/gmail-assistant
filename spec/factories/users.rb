# frozen_string_literal: true

FactoryBot.define do
  factory :user do
    sequence(:email) { |n| "user#{n}@example.com" }
    display_name { "Test User" }
    is_active { true }
    onboarded_at { nil }

    trait :onboarded do
      onboarded_at { 1.day.ago }
    end

    trait :inactive do
      is_active { false }
    end
  end
end
