# frozen_string_literal: true

namespace :sync do
  desc "Trigger a full inbox sync. Usage: rake sync:full[user_id]"
  task :full, [:user_id] => :environment do |_t, args|
    user = args[:user_id] ? User.find(args[:user_id]) : User.first

    unless user
      puts "\e[31mERROR: No users found. Run OAuth setup first.\e[0m"
      exit 1
    end

    puts "\e[36m=== Full Sync Trigger ===\e[0m"
    puts "User: #{user.email}"
    puts ""

    # Clear sync state to force full scan
    sync_state = user.sync_state
    if sync_state
      old_history_id = sync_state.last_history_id
      sync_state.update!(last_history_id: "0")
      puts "Cleared sync state (was: history_id=#{old_history_id})"
    end

    # Enqueue sync job
    SyncJob.perform_later(user.id, "full" => true)
    puts "\e[32mSync job enqueued. Monitor server logs for progress.\e[0m"
  end

  desc "Trigger a full inbox sync with database reset. Usage: rake sync:reset_and_sync[user_id]"
  task :reset_and_sync, [:user_id] => :environment do |_t, args|
    user = args[:user_id] ? User.find(args[:user_id]) : User.first

    unless user
      puts "\e[31mERROR: No users found.\e[0m"
      exit 1
    end

    puts "\e[36m=== Reset and Full Sync ===\e[0m"
    puts "User: #{user.email}"
    puts ""

    if ENV["RAILS_ENV"] == "production"
      print "\e[31mWARNING: This will delete all transient data in production. Continue? (yes/no): \e[0m"
      confirmation = $stdin.gets&.chomp
      unless confirmation == "yes"
        puts "Aborted."
        exit 0
      end
    end

    # Delete transient data
    counts = {}
    counts[:email_events] = EmailEvent.where(user: user).delete_all
    counts[:llm_calls] = LlmCall.where(user: user).delete_all
    counts[:agent_runs] = AgentRun.where(user: user).delete_all
    counts[:emails] = Email.where(user: user).delete_all

    sync_state = user.sync_state
    sync_state&.update!(last_history_id: "0")

    puts "Deleted transient data:"
    counts.each do |table, count|
      puts "  #{table}: #{count} rows"
    end
    puts "  sync_state: reset to 0"
    puts ""

    # Enqueue sync job
    SyncJob.perform_later(user.id, "full" => true)
    puts "\e[32mSync job enqueued. Monitor server logs for progress.\e[0m"
  end
end
