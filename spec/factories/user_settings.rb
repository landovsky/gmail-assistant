# frozen_string_literal: true

FactoryBot.define do
  factory :user_setting do
    user
    sequence(:key) { |n| "setting_#{n}" }
    value { '{"default": true}' }

    trait :communication_styles do
      key { "communication_styles" }
      value { '{"formal": {"register": "formal"}, "business": {"register": "business"}}' }
    end

    trait :sign_off_name do
      key { "sign_off_name" }
      value { '"Test User"' }
    end

    trait :default_language do
      key { "default_language" }
      value { '"cs"' }
    end
  end
end
