# frozen_string_literal: true

FactoryBot.define do
  factory :sync_state do
    user
    last_history_id { "0" }
    last_sync_at { nil }
    watch_expiration { nil }
    watch_resource_id { nil }

    trait :synced do
      last_history_id { "12345" }
      last_sync_at { 5.minutes.ago }
    end

    trait :watching do
      watch_expiration { 6.days.from_now }
      watch_resource_id { "resource_123" }
    end
  end
end
