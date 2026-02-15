# frozen_string_literal: true

namespace :db_management do
  desc "Clear all transient data while preserving user accounts and configuration"
  task reset: :environment do
    puts "\e[36m=== Database Reset ===\e[0m"
    puts ""

    if ENV["RAILS_ENV"] == "production"
      print "\e[31mWARNING: This will delete all transient data in production. Continue? (yes/no): \e[0m"
      confirmation = $stdin.gets&.chomp
      unless confirmation == "yes"
        puts "Aborted."
        exit 0
      end
    end

    counts = {}

    # Clear Sidekiq queues and scheduled jobs
    require "sidekiq/api"
    queues_cleared = 0
    Sidekiq::Queue.all.each do |queue|
      queues_cleared += queue.size
      queue.clear
    end
    scheduled_cleared = Sidekiq::ScheduledSet.new.size
    Sidekiq::ScheduledSet.new.clear
    retries_cleared = Sidekiq::RetrySet.new.size
    Sidekiq::RetrySet.new.clear
    dead_cleared = Sidekiq::DeadSet.new.size
    Sidekiq::DeadSet.new.clear
    puts "Sidekiq cleared: #{queues_cleared} queued, #{scheduled_cleared} scheduled, #{retries_cleared} retries, #{dead_cleared} dead"
    puts ""

    # Delete in dependency order
    counts[:jobs] = Job.delete_all
    counts[:email_events] = EmailEvent.delete_all
    counts[:llm_calls] = LlmCall.delete_all
    counts[:agent_runs] = AgentRun.delete_all
    counts[:emails] = Email.delete_all

    # Reset sync states
    SyncState.update_all(last_history_id: "0")
    counts[:sync_states_reset] = SyncState.count

    puts "Deleted transient data:"
    counts.each do |table, count|
      puts "  #{table}: #{count} rows"
    end

    total = counts.values.sum
    puts ""
    puts "\e[32mTotal: #{total} rows deleted.\e[0m"
    puts ""
    puts "Preserved: users, user_labels, user_settings"
  end

  desc "Show database statistics"
  task stats: :environment do
    puts "\e[36m=== Database Statistics ===\e[0m"
    puts ""

    tables = {
      "Users" => User,
      "Emails" => Email,
      "EmailEvents" => EmailEvent,
      "LlmCalls" => LlmCall,
      "AgentRuns" => AgentRun,
      "UserLabels" => UserLabel,
      "UserSettings" => UserSetting,
      "SyncStates" => SyncState
    }

    tables.each do |name, model|
      count = model.count
      puts "  #{name.ljust(15)} #{count}"
    end

    puts ""

    if Email.any?
      puts "\e[33mEmail Breakdown:\e[0m"
      Email.group(:classification).count.sort_by { |_, v| -v }.each do |classification, count|
        puts "  #{classification.ljust(20)} #{count}"
      end
      puts ""
      Email.group(:status).count.sort_by { |_, v| -v }.each do |status, count|
        puts "  #{status.ljust(20)} #{count}"
      end
    end

    if LlmCall.any?
      puts ""
      puts "\e[33mLLM Call Stats:\e[0m"
      total_tokens = LlmCall.sum(:prompt_tokens) + LlmCall.sum(:completion_tokens)
      avg_latency = LlmCall.average(:latency_ms)&.round(0)
      puts "  Total calls:    #{LlmCall.count}"
      puts "  Total tokens:   #{total_tokens}"
      puts "  Avg latency:    #{avg_latency}ms"
      puts "  By type:"
      LlmCall.group(:call_type).count.each do |type, count|
        puts "    #{type.ljust(15)} #{count}"
      end
    end
  end
end
