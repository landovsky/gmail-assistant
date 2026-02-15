# frozen_string_literal: true

module Debug
  class EmailsController < ApplicationController
    skip_before_action :verify_authenticity_token, raise: false
    before_action :authenticate!
    layout "debug"

    # GET /debug/emails
    def index
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

      # Sorting
      sort_column = params[:sort] || "id"
      sort_direction = params[:direction] || "desc"

      # Validate sort parameters
      allowed_columns = %w[id classification status confidence received_at resolved_style]
      sort_column = "id" unless allowed_columns.include?(sort_column)
      sort_direction = "desc" unless %w[asc desc].include?(sort_direction)

      scope = scope.order("#{sort_column} #{sort_direction}")

      # Pagination
      per_page = 50
      page = (params[:page] || 1).to_i
      page = 1 if page < 1

      @total_count = scope.count
      @total_pages = (@total_count.to_f / per_page).ceil
      @current_page = page
      @per_page = per_page

      @emails = scope.limit(per_page).offset((page - 1) * per_page)
      @filters = {
        status: params[:status],
        classification: params[:classification],
        q: params[:q],
        sort: sort_column,
        direction: sort_direction
      }
    end

    # GET /debug/email/:id
    def show
      @email = Email.find(params[:id])

      @events = EmailEvent.where(user_id: @email.user_id, gmail_thread_id: @email.gmail_thread_id)
                          .order(created_at: :asc)
      @llm_calls = LlmCall.where(user_id: @email.user_id, gmail_thread_id: @email.gmail_thread_id)
                          .order(created_at: :desc)
      @agent_runs = AgentRun.where(user_id: @email.user_id, gmail_thread_id: @email.gmail_thread_id)
                            .order(created_at: :asc)

      @timeline = build_timeline
      @prev_email = Email.where("id < ?", @email.id).order(id: :desc).first
      @next_email = Email.where("id > ?", @email.id).order(id: :asc).first
    end

    private

    def authenticate!
      admin_user = AppConfig.server.admin_user
      admin_password = AppConfig.server.admin_password
      return if admin_user.blank? || admin_password.blank?

      authenticate_or_request_with_http_basic("Gmail Assistant") do |username, password|
        ActiveSupport::SecurityUtils.secure_compare(username, admin_user) &
          ActiveSupport::SecurityUtils.secure_compare(password, admin_password)
      end
    end

    def build_timeline
      items = []

      @events.each do |event|
        items << {
          type: :event,
          timestamp: event.created_at,
          event_type: event.event_type,
          detail: event.detail,
          label_id: event.label_id,
          draft_id: event.draft_id
        }
      end

      @llm_calls.each do |call|
        items << {
          type: :llm_call,
          timestamp: call.created_at,
          call_type: call.call_type,
          model: call.model,
          latency_ms: call.latency_ms,
          total_tokens: call.total_tokens,
          prompt_tokens: call.prompt_tokens,
          completion_tokens: call.completion_tokens,
          success: call.successful?,
          error: call.error
        }
      end

      @agent_runs.each do |run|
        items << {
          type: :agent_run,
          timestamp: run.created_at,
          profile: run.profile,
          status: run.status,
          iterations: run.iterations,
          error: run.error
        }
      end

      items.sort_by { |item| item[:timestamp] }.reverse
    end
  end
end
