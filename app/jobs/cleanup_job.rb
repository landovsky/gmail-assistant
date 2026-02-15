# frozen_string_literal: true

class CleanupJob < ApplicationJob
  queue_as :low
  retry_on StandardError, wait: :polynomially_longer, attempts: 3

  # Runs periodic cleanup: stale jobs, sent detection, draft cleanup
  def perform(user_id = nil)
    if user_id
      cleanup_user(User.find(user_id))
    else
      User.active.find_each { |user| cleanup_user(user) }
    end
  end

  private

  def cleanup_user(user)
    cleanup_stale_jobs
    detect_sent_drafts(user)
  end

  def cleanup_stale_jobs
    deleted_count = Job.stale.delete_all
    Rails.logger.info("Cleaned up #{deleted_count} stale jobs") if deleted_count.positive?
  end

  def detect_sent_drafts(user)
    gmail_client = Gmail::Client.new(user: user)

    user.emails.drafted.find_each do |email|
      next unless email.draft_id.present?

      begin
        gmail_client.get_draft(email.draft_id)
      rescue Gmail::Client::NotFoundError
        # Draft was deleted/sent
        email.mark_sent!
        email.log_event("sent_detected", "Draft no longer exists, marking as sent")

        # Clean up labels
        label_manager = Gmail::LabelManager.new(user: user, gmail_client: gmail_client)
        label_manager.remove_label(message_id: email.gmail_message_id, label_key: "outbox")
        label_manager.apply_workflow_label(message_id: email.gmail_message_id, label_key: "done")
      rescue Gmail::Client::GmailApiError => e
        Rails.logger.error("Error checking draft #{email.draft_id}: #{e.message}")
      end
    end
  end
end
