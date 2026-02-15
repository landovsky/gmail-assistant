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

    # Build label_id -> name lookup
    label_names = user.user_labels.each_with_object({}) { |ul, h| h[ul.gmail_label_id] = ul.label_key }

    puts "AI labels to clean:"
    label_names.each do |gmail_id, name|
      puts "  #{name} (#{gmail_id})"
    end
    puts ""

    all_message_ids = Set.new
    ai_label_ids.each do |label_id|
      begin
        response = gmail_client.list_messages(label_ids: [label_id], max_results: 500)
        messages = response.messages || []
        next if messages.empty?

        msg_ids = messages.map(&:id)
        all_message_ids.merge(msg_ids)
        puts "#{label_names[label_id] || label_id}: #{messages.size} messages"

        messages.first(5).each do |msg_ref|
          begin
            message = gmail_client.get_message(msg_ref.id, format: "metadata")
            parsed = Gmail::MessageParser.parse(message)
            puts "  - #{parsed[:subject]&.truncate(60)}"
          rescue StandardError
            puts "  - Message #{msg_ref.id}"
          end
        end
        puts "  ..." if messages.size > 5
      rescue Gmail::Client::GmailApiError => e
        puts "\e[31m  Error for label #{label_id}: #{e.message}\e[0m"
      end
    end

    puts ""
    if all_message_ids.empty?
      puts "\e[32mNo messages with AI labels found.\e[0m"
    elsif mode == "delete"
      gmail_client.batch_modify_message_labels(
        all_message_ids.to_a,
        remove_label_ids: ai_label_ids
      )
      puts "\e[32mCleaned #{all_message_ids.size} messages (batch API).\e[0m"
    else
      puts "#{all_message_ids.size} unique messages would be affected."
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

      if ai_drafts.empty?
        puts "\e[32mNo AI-generated drafts found (checked #{drafts.drafts.size} drafts).\e[0m"
      else
        puts "Found #{ai_drafts.size} AI-generated drafts (out of #{drafts.drafts.size} total):"
        puts ""

        ai_drafts.each do |d|
          puts "  - #{d[:subject] || '(no subject)'}"
        end

        if mode == "delete"
          puts ""
          ai_drafts.each do |d|
            gmail_client.delete_draft(d[:id])
            puts "\e[31m  Deleted: #{d[:subject]}\e[0m"
          end
          puts "\e[32m\nDeleted #{ai_drafts.size} AI drafts.\e[0m"
        else
          puts "\n\e[33mRun with mode=delete to apply: rake gmail:cleanup_drafts[#{user.id},delete]\e[0m"
        end
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

  # Note: Google API gem auto-decodes base64 body data, so .data is already UTF-8
  if payload.body&.data.present?
    payload.body.data.force_encoding("UTF-8")
  elsif payload.parts
    text_part = payload.parts.find { |p| p.mime_type == "text/plain" }
    html_part = payload.parts.find { |p| p.mime_type == "text/html" }
    part = text_part || html_part
    part&.body&.data.present? ? part.body.data.force_encoding("UTF-8") : nil
  end
rescue StandardError
  nil
end

def extract_draft_subject(draft)
  headers = draft.message&.payload&.headers || []
  subject_header = headers.find { |h| h.name&.downcase == "subject" }
  subject_header&.value
end
