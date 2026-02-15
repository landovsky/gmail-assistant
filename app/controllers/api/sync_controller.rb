# frozen_string_literal: true

module Api
  class SyncController < BaseController
    # POST /api/sync
    # Enqueue a sync job for a user.
    def create
      user_id = params[:user_id] || 1
      full = params[:full] == "true"

      user = User.find_by(id: user_id)
      unless user
        render json: { detail: "User #{user_id} not found. Run POST /api/auth/init first." }, status: :not_found
        return
      end

      # Force full sync by resetting history ID
      if full
        user.sync_state.update!(last_history_id: "0")
      end

      SyncJob.perform_later(user.id)

      render json: {
        queued: true,
        user_id: user.id,
        full: full
      }
    end
  end
end
