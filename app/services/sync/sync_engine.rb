# frozen_string_literal: true

module Sync
  # Gmail sync engine using History API for incremental sync.
  # Detects new messages, label changes, and triggers classification/rework jobs.
  class SyncEngine
    def initialize(user:, gmail_client: nil)
      @user = user
      @gmail_client = gmail_client || Gmail::Client.new(user: user)
      @label_manager = Gmail::LabelManager.new(user: user, gmail_client: @gmail_client)
    end

    # Perform incremental sync using History API.
    # Falls back to full sync if history ID is expired.
    def sync!
      sync_state = @user.sync_state

      if sync_state.needs_full_sync?
        full_sync!
      else
        incremental_sync!(sync_state)
      end
    end

    # Full sync: list recent INBOX messages and process them.
    def full_sync!
      Rails.logger.info("Full sync for user #{@user.email}")

      response = @gmail_client.list_messages(
        label_ids: ["INBOX"],
        max_results: AppConfig.sync.history_max_results
      )

      if response.messages
        response.messages.each do |msg_ref|
          process_new_message(msg_ref.id)
        rescue => e
          Rails.logger.error("Error processing message #{msg_ref.id}: #{e.message}")
        end
      end

      # Always get the latest history ID from profile, even if no messages
      profile = @gmail_client.get_profile
      @user.sync_state.update_history_id!(profile.history_id.to_s)
    end

    # Incremental sync using History API.
    def incremental_sync!(sync_state)
      Rails.logger.info("Incremental sync for user #{@user.email} from history #{sync_state.last_history_id}")

      begin
        response = @gmail_client.list_history(
          start_history_id: sync_state.last_history_id,
          history_types: %w[messageAdded labelAdded labelRemoved],
          max_results: AppConfig.sync.history_max_results
        )
      rescue Gmail::Client::NotFoundError
        # History ID expired, fall back to full sync
        Rails.logger.warn("History ID expired, falling back to full sync")
        sync_state.update!(last_history_id: "0")
        return full_sync!
      end

      process_history_events(response) if response.history

      # Update history ID
      new_history_id = response.history_id || sync_state.last_history_id
      sync_state.update_history_id!(new_history_id.to_s)
    end

    private

    def process_history_events(response)
      response.history.each do |history_record|
        # Process new messages
        history_record.messages_added&.each do |added|
          process_new_message(added.message.id)
        rescue => e
          Rails.logger.error("Error processing added message: #{e.message}")
        end

        # Process label changes
        history_record.labels_added&.each do |label_change|
          process_label_added(label_change)
        rescue => e
          Rails.logger.error("Error processing label added: #{e.message}")
        end

        history_record.labels_removed&.each do |label_change|
          process_label_removed(label_change)
        rescue => e
          Rails.logger.error("Error processing label removed: #{e.message}")
        end
      end
    end

    def process_new_message(message_id)
      message = @gmail_client.get_message(message_id, format: "full")
      parsed = Gmail::MessageParser.parse(message)

      # Check if this thread already exists
      existing = @user.emails.find_by(gmail_thread_id: parsed[:gmail_thread_id])

      if existing
        handle_thread_update(existing, parsed, message)
      else
        enqueue_classification(parsed)
      end
    end

    def handle_thread_update(email, parsed, _message)
      # Update message count
      new_count = email.message_count + 1
      email.update!(
        gmail_message_id: parsed[:gmail_message_id],
        message_count: new_count
      )

      # If waiting, new reply triggers reclassification
      if email.status == "pending" && email.classification == "waiting"
        email.log_event("waiting_retriaged", "New reply detected on waiting thread")
        Job.enqueue(
          job_type: "classify",
          user: @user,
          payload: { email_id: email.id, force: true }
        )
      end
    end

    def enqueue_classification(parsed_data)
      payload = {
        gmail_thread_id: parsed_data[:gmail_thread_id],
        gmail_message_id: parsed_data[:gmail_message_id],
        sender_email: parsed_data[:sender_email],
        sender_name: parsed_data[:sender_name],
        subject: parsed_data[:subject],
        snippet: parsed_data[:snippet],
        received_at: parsed_data[:received_at]&.iso8601
      }

      # Record in internal job table for tracking
      Job.enqueue(
        job_type: "classify",
        user: @user,
        payload: payload
      )

      # Dispatch to Sidekiq for actual processing
      ClassifyJob.perform_later(@user.id, payload.stringify_keys)
    end

    def process_label_added(label_change)
      message = label_change.message
      label_ids = label_change.label_ids || []

      # Check for rework label
      rework_label = @user.label_for("rework")
      if rework_label && label_ids.include?(rework_label.gmail_label_id)
        handle_rework_request(message)
      end

      # Check for done label
      done_label = @user.label_for("done")
      if done_label && label_ids.include?(done_label.gmail_label_id)
        handle_done_label(message)
      end

      # Check for needs_response label (manual draft request)
      nr_label = @user.label_for("needs_response")
      if nr_label && label_ids.include?(nr_label.gmail_label_id)
        handle_manual_draft_request(message)
      end
    end

    def process_label_removed(_label_change)
      # Currently no action needed for label removal
    end

    def handle_rework_request(message)
      email = @user.emails.find_by(gmail_message_id: message.id)
      return unless email&.status == "drafted"

      # Extract rework instruction from draft (would need to fetch draft content)
      Job.enqueue(
        job_type: "rework",
        user: @user,
        payload: { email_id: email.id }
      )
    end

    def handle_done_label(message)
      email = @user.emails.find_by(gmail_message_id: message.id)
      return unless email

      email.mark_archived!
      email.log_event("archived", "User marked as done")
    end

    def handle_manual_draft_request(message)
      email = @user.emails.find_by(gmail_message_id: message.id)
      return if email&.status == "drafted" # Already has a draft

      Job.enqueue(
        job_type: "manual_draft",
        user: @user,
        payload: { gmail_message_id: message.id }
      )
    end
  end
end
