# frozen_string_literal: true

FactoryBot.define do
  factory :user_label do
    user
    sequence(:label_key) { |n| "label_#{n}" }
    sequence(:gmail_label_id) { |n| "Label_#{n}" }
    sequence(:gmail_label_name) { |n| "GMA/Label #{n}" }

    trait :needs_response do
      label_key { "needs_response" }
      gmail_label_name { "GMA/Needs Response" }
    end

    trait :outbox do
      label_key { "outbox" }
      gmail_label_name { "GMA/Outbox" }
    end

    trait :rework do
      label_key { "rework" }
      gmail_label_name { "GMA/Rework" }
    end

    trait :done do
      label_key { "done" }
      gmail_label_name { "GMA/Done" }
    end
  end
end
