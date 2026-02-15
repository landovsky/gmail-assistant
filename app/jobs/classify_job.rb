# frozen_string_literal: true

class ClassifyJob < ApplicationJob
  queue_as :default
  retry_on StandardError, wait: :polynomially_longer, attempts: 3

  def perform(user_id, payload)
    user = User.find(user_id)
    payload = payload.symbolize_keys

    # Find matching internal Job record to track status
    internal_job = Job.pending.find_by(
      job_type: "classify",
      user: user,
      payload: payload.to_json
    )
    internal_job&.claim!

    # If we have an email_id, it's a reclassification
    if payload[:email_id]
      email = user.emails.find(payload[:email_id])
      pipeline = Classification::Pipeline.new(user: user)
      pipeline.reclassify(email)
      internal_job&.complete!
      return
    end

    # Otherwise, classify new email data
    pipeline = Classification::Pipeline.new(user: user)
    pipeline.classify(
      email_data: {
        gmail_thread_id: payload[:gmail_thread_id],
        gmail_message_id: payload[:gmail_message_id],
        sender_email: payload[:sender_email],
        sender_name: payload[:sender_name],
        subject: payload[:subject],
        snippet: payload[:snippet],
        received_at: payload[:received_at] ? Time.zone.parse(payload[:received_at]) : nil
      }
    )

    internal_job&.complete!

    # If classified as needs_response, enqueue draft job
    email = user.emails.find_by(gmail_thread_id: payload[:gmail_thread_id])
    if email&.can_draft?
      DraftJob.perform_later(user_id, { "email_id" => email.id })
    end
  rescue => e
    internal_job&.fail!(e.message)
    raise
  end
end
