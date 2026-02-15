# frozen_string_literal: true

module Webhook
  class GmailController < ApplicationController
    skip_before_action :verify_authenticity_token

    # POST /webhook/gmail
    # Receives Gmail Pub/Sub push notifications and triggers sync for the affected user.
    def create
      notification = parse_notification

      unless notification
        render json: { error: "Invalid notification" }, status: :bad_request
        return
      end

      user_email = notification[:email_address]
      history_id = notification[:history_id]

      user = User.find_by(email: user_email)
      unless user
        Rails.logger.warn("Webhook received for unknown user: #{user_email}")
        head :ok # Return 200 to prevent retries
        return
      end

      Rails.logger.info("Gmail webhook for #{user_email}, history_id: #{history_id}")

      # Enqueue sync job
      SyncJob.perform_later(user.id)

      head :ok
    end

    private

    def parse_notification
      body = request.body.read
      data = JSON.parse(body)

      # Google Pub/Sub wraps the message in a "message" key
      message = data["message"]
      return nil unless message

      # Decode the base64 data
      decoded = Base64.decode64(message["data"] || "")
      payload = JSON.parse(decoded)

      {
        email_address: payload["emailAddress"],
        history_id: payload["historyId"]
      }
    rescue JSON::ParserError, ArgumentError => e
      Rails.logger.error("Failed to parse webhook: #{e.message}")
      nil
    end
  end
end
