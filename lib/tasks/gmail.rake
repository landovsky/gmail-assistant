# frozen_string_literal: true

namespace :gmail do
  desc "Remove all AI labels from inbox messages. Usage: rake gmail:cleanup_labels[user_id] (dry run by default)"
  task :cleanup_labels, [:user_id, :mode] => :environment do |_t, args|
    mode = args[:mode] || "dry_run"
    user = find_user(args[:user_id])

    puts "\e[36m=== Gmail Label Cleanup ===\e[0m"
    puts "User: #{user.email}"
    puts "Mode: #{mode == 'delete' ? "\e[31mDELETE\e[0m" : "\e[33mDRY RUN\e[0m"}"
    puts ""

    gmail_client = Gmail::Client.new(user: user)
    ai_label_ids = user.user_labels.pluck(:gmail_label_id).compact

    if ai_label_ids.empty?
      puts "No AI labels found for this user."
      exit 0
    end

    puts "AI labels to clean:"
    user.user_labels.each do |ul|
      puts "  #{ul.label_key}: #{ul.gmail_label_id}"
    end
    puts ""

    total_affected = 0
    ai_label_ids.each do |label_id|
      begin
        response = gmail_client.list_messages(label_ids: [label_id], max_results: 500)
        messages = response.messages || []
        next if messages.empty?

        total_affected += messages.size
        puts "Label #{label_id}: #{messages.size} messages"

        messages.first(5).each do |msg_ref|
          begin
            message = gmail_client.get_message(msg_ref.id, format: "metadata")
            parsed = Gmail::MessageParser.parse(message)
            puts "  - #{parsed[:subject]&.truncate(60)} (#{msg_ref.id})"
          rescue StandardError
            puts "  - Message #{msg_ref.id}"
          end
        end
        puts "  ..." if messages.size > 5

        if mode == "delete"
          messages.each do |msg_ref|
            gmail_client.modify_message(
              msg_ref.id,
              remove_label_ids: ai_label_ids
            )
          end
          puts "  \e[32mLabels removed.\e[0m"
        end
      rescue Gmail::Client::GmailApiError => e
        puts "\e[31m  Error for label #{label_id}: #{e.message}\e[0m"
      end
    end

    puts ""
    if mode == "delete"
      puts "\e[32mCleaned #{total_affected} messages.\e[0m"
    else
      puts "#{total_affected} messages would be affected."
      puts "\e[33mRun with mode=delete to apply: rake gmail:cleanup_labels[#{user.id},delete]\e[0m"
    end
  end

  desc "Delete AI-generated drafts (with rework marker). Usage: rake gmail:cleanup_drafts[user_id] (dry run by default)"
  task :cleanup_drafts, [:user_id, :mode] => :environment do |_t, args|
    mode = args[:mode] || "dry_run"
    user = find_user(args[:user_id])

    puts "\e[36m=== Gmail Draft Cleanup ===\e[0m"
    puts "User: #{user.email}"
    puts "Mode: #{mode == 'delete' ? "\e[31mDELETE\e[0m" : "\e[33mDRY RUN\e[0m"}"
    puts ""

    # The rework marker that identifies AI-generated drafts
    rework_marker = "\u2702\uFE0F" # ✂️

    gmail_client = Gmail::Client.new(user: user)

    begin
      drafts = gmail_client.list_drafts
      unless drafts&.drafts
        puts "No drafts found."
        exit 0
      end

      ai_drafts = []
      drafts.drafts.each do |draft_ref|
        begin
          draft = gmail_client.get_draft(draft_ref.id)
          body = extract_draft_body(draft)
          if body&.include?(rework_marker)
            ai_drafts << { id: draft_ref.id, subject: extract_draft_subject(draft), body_preview: body.truncate(100) }
          end
        rescue StandardError => e
          puts "\e[33m  Warning: Could not read draft #{draft_ref.id}: #{e.message}\e[0m"
        end
      end

      puts "Total drafts: #{drafts.drafts.size}"
      puts "AI-generated drafts (with rework marker): #{ai_drafts.size}"
      puts ""

      ai_drafts.each do |d|
        puts "  - #{d[:subject] || '(no subject)'}"
      end

      if mode == "delete" && ai_drafts.any?
        puts ""
        ai_drafts.each do |d|
          gmail_client.delete_draft(d[:id])
          puts "\e[31m  Deleted: #{d[:subject]}\e[0m"
        end
        puts "\e[32m\nDeleted #{ai_drafts.size} AI drafts.\e[0m"
      elsif ai_drafts.any?
        puts "\n\e[33mRun with mode=delete to apply: rake gmail:cleanup_drafts[#{user.id},delete]\e[0m"
      end
    rescue Gmail::Client::GmailApiError => e
      puts "\e[31mGmail API error: #{e.message}\e[0m"
      exit 1
    end
  end
end

def find_user(user_id)
  if user_id
    User.find(user_id)
  else
    user = User.first
    unless user
      puts "\e[31mERROR: No users found.\e[0m"
      exit 1
    end
    user
  end
end

def extract_draft_body(draft)
  message = draft.message
  return nil unless message

  payload = message.payload
  return nil unless payload

  if payload.body&.data
    Base64.urlsafe_decode64(payload.body.data)
  elsif payload.parts
    text_part = payload.parts.find { |p| p.mime_type == "text/plain" }
    text_part&.body&.data ? Base64.urlsafe_decode64(text_part.body.data) : nil
  end
rescue StandardError
  nil
end

def extract_draft_subject(draft)
  headers = draft.message&.payload&.headers || []
  subject_header = headers.find { |h| h.name&.downcase == "subject" }
  subject_header&.value
end
