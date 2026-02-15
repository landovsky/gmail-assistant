# frozen_string_literal: true

module Api
  class DebugController < BaseController
    # GET /api/debug/emails
    # List emails with search, filter, and per-email debug counts.
    def emails
      limit = [params.fetch(:limit, 50).to_i, 500].min
      scope = Email.includes(:user)

      if params[:status].present?
        scope = scope.by_status(params[:status])
      end

      if params[:classification].present?
        scope = scope.by_classification(params[:classification])
      end

      if params[:q].present?
        query = "%#{params[:q]}%"
        scope = scope.where(
          "subject LIKE :q OR snippet LIKE :q OR reasoning LIKE :q OR sender_email LIKE :q OR gmail_thread_id LIKE :q",
          q: query
        )
      end

      email_records = scope.order(id: :desc).limit(limit)

      emails_json = email_records.map do |email|
        {
          id: email.id,
          user_id: email.user_id,
          user_email: email.user.email,
          gmail_thread_id: email.gmail_thread_id,
          subject: email.subject,
          sender_email: email.sender_email,
          classification: email.classification,
          status: email.status,
          confidence: email.confidence,
          received_at: email.received_at,
          processed_at: email.processed_at,
          event_count: EmailEvent.where(user_id: email.user_id, gmail_thread_id: email.gmail_thread_id).count,
          llm_call_count: LlmCall.where(user_id: email.user_id, gmail_thread_id: email.gmail_thread_id).count,
          agent_run_count: AgentRun.where(user_id: email.user_id, gmail_thread_id: email.gmail_thread_id).count
        }
      end

      render json: {
        count: emails_json.size,
        limit: limit,
        filters: {
          status: params[:status],
          classification: params[:classification],
          q: params[:q]
        },
        emails: emails_json
      }
    end

    # GET /api/emails/:id/debug
    # Get all debug data for a specific email.
    def show
      email = Email.find(params[:id])

      events = EmailEvent.where(user_id: email.user_id, gmail_thread_id: email.gmail_thread_id)
                         .order(created_at: :asc)
      llm_calls = LlmCall.where(user_id: email.user_id, gmail_thread_id: email.gmail_thread_id)
                         .order(created_at: :asc)
      agent_runs = AgentRun.where(user_id: email.user_id, gmail_thread_id: email.gmail_thread_id)
                           .order(created_at: :asc)

      # Build timeline (merged and sorted by created_at)
      timeline = build_timeline(events, llm_calls, agent_runs)

      # Build summary
      summary = build_debug_summary(email, events, llm_calls, agent_runs)

      render json: {
        email: email.as_json(except: %i[created_at updated_at]),
        events: events.as_json,
        llm_calls: llm_calls.as_json,
        agent_runs: agent_runs.as_json,
        timeline: timeline,
        summary: summary
      }
    end

    private

    def build_timeline(events, llm_calls, agent_runs)
      items = []

      events.each do |event|
        items << {
          type: "event",
          timestamp: event.created_at,
          event_type: event.event_type,
          detail: event.detail
        }
      end

      llm_calls.each do |call|
        items << {
          type: "llm_call",
          timestamp: call.created_at,
          call_type: call.call_type,
          model: call.model,
          latency_ms: call.latency_ms,
          total_tokens: call.total_tokens,
          success: call.successful?
        }
      end

      agent_runs.each do |run|
        items << {
          type: "agent_run",
          timestamp: run.created_at,
          profile: run.profile,
          status: run.status,
          iterations: run.iterations
        }
      end

      items.sort_by { |item| item[:timestamp] }
    end

    def build_debug_summary(email, events, llm_calls, agent_runs)
      llm_breakdown = llm_calls.group_by(&:call_type).transform_values do |calls|
        {
          count: calls.size,
          tokens: calls.sum(&:total_tokens),
          latency_ms: calls.sum(&:latency_ms)
        }
      end

      {
        email_id: email.id,
        gmail_thread_id: email.gmail_thread_id,
        classification: email.classification,
        status: email.status,
        event_count: events.size,
        llm_call_count: llm_calls.size,
        agent_run_count: agent_runs.size,
        total_tokens: llm_calls.sum(&:total_tokens),
        total_latency_ms: llm_calls.sum(&:latency_ms),
        error_count: llm_calls.count { |c| !c.successful? },
        llm_breakdown: llm_breakdown,
        rework_count: email.rework_count
      }
    end
  end
end
