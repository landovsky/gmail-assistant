# frozen_string_literal: true

module Api
  class WatchController < BaseController
    # POST /api/watch
    # Register Gmail push notifications for one or all active users.
    def create
      pubsub_topic = AppConfig.get(:sync, :pubsub_topic)

      unless pubsub_topic.present?
        render json: { detail: "No pubsub_topic configured in config section" }, status: :bad_request
        return
      end

      if params[:user_id].present?
        user = User.find(params[:user_id])
        result = register_watch(user, pubsub_topic)
        render json: result
      else
        results = User.active.map { |user| register_watch(user, pubsub_topic) }
        render json: { results: results }
      end
    end

    # GET /api/watch/status
    # Show watch state for all users.
    def status
      users = User.active.includes(:sync_state)
      statuses = users.map do |user|
        sync = user.sync_state
        {
          user_id: user.id,
          email: user.email,
          last_history_id: sync.last_history_id,
          last_sync_at: sync.last_sync_at,
          watch_expiration: sync.watch_expiration,
          watch_resource_id: sync.watch_resource_id
        }
      end
      render json: statuses
    end

    private

    def register_watch(user, pubsub_topic)
      gmail_client = Gmail::Client.new(user: user)
      response = gmail_client.watch(
        topic_name: pubsub_topic,
        label_ids: ["INBOX"]
      )

      user.sync_state.update_watch!(
        expiration: Time.at(response.expiration.to_i / 1000),
        resource_id: response.history_id.to_s
      )

      {
        user_id: user.id,
        email: user.email,
        watch_registered: true
      }
    rescue StandardError => e
      Rails.logger.error("Watch registration failed for #{user.email}: #{e.message}")
      {
        user_id: user.id,
        email: user.email,
        watch_registered: false,
        error: e.message
      }
    end
  end
end
