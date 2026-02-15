# frozen_string_literal: true

module Api
  class ResetController < BaseController
    # POST /api/reset
    # Reset transient data (preserves users, labels, settings).
    def create
      deleted = {
        jobs: Job.delete_all,
        emails: Email.delete_all,
        email_events: EmailEvent.delete_all,
        llm_calls: LlmCall.delete_all,
        agent_runs: AgentRun.delete_all
      }

      # Reset sync state history IDs
      sync_count = SyncState.update_all(
        last_history_id: "0",
        last_sync_at: nil,
        watch_expiration: nil,
        watch_resource_id: nil
      )
      deleted[:sync_state] = sync_count

      total = deleted.values.sum

      render json: {
        deleted: deleted,
        total: total
      }
    end
  end
end
