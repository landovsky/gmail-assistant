# frozen_string_literal: true

FactoryBot.define do
  factory :job do
    user
    job_type { "classify" }
    payload { "{}" }
    status { "pending" }
    attempts { 0 }
    max_attempts { 3 }

    trait :running do
      status { "running" }
      started_at { 1.minute.ago }
      attempts { 1 }
    end

    trait :completed do
      status { "completed" }
      started_at { 2.minutes.ago }
      completed_at { 1.minute.ago }
      attempts { 1 }
    end

    trait :failed do
      status { "failed" }
      started_at { 2.minutes.ago }
      completed_at { 1.minute.ago }
      attempts { 3 }
      error_message { "Maximum attempts reached" }
    end

    Job::JOB_TYPES.each do |type|
      trait type.to_sym do
        job_type { type }
      end
    end
  end
end
