# frozen_string_literal: true

module Api
  class EmailsController < BaseController
    # POST /api/emails/:id/reclassify
    # Force reclassification of an email.
    def reclassify
      email = Email.find(params[:id])

      unless email.gmail_message_id.present?
        render json: { detail: "Email has no Gmail message ID" }, status: :bad_request
        return
      end

      job = Job.enqueue(
        job_type: "classify",
        user: email.user,
        payload: { email_id: email.id, force: true }
      )

      ClassifyJob.perform_later(email.user_id, { "email_id" => email.id, "force" => true })

      render json: {
        status: "queued",
        job_id: job.id,
        email_id: email.id,
        current_classification: email.classification
      }
    end
  end
end
