# frozen_string_literal: true

module Api
  class UsersController < BaseController
    # GET /api/users
    def index
      users = User.active.select(:id, :email, :display_name, :onboarded_at)
      render json: users
    end

    # POST /api/users
    def create
      email = json_body[:email]
      display_name = json_body[:display_name]

      if User.exists?(email: email)
        render json: { detail: "User already exists" }, status: :conflict
        return
      end

      user = User.create!(email: email, display_name: display_name)
      render json: { id: user.id, email: user.email }
    end

    # GET /api/users/:id/settings
    def settings
      user = User.find(params[:id])
      settings_hash = user.user_settings.each_with_object({}) do |setting, hash|
        hash[setting.key] = setting.parsed_value
      end
      render json: settings_hash
    end

    # PUT /api/users/:id/settings
    def update_settings
      user = User.find(params[:id])
      key = json_body[:key]
      value = json_body[:value]

      setting = user.user_settings.find_or_initialize_by(key: key)
      setting.parsed_value = value
      setting.save!

      render json: { ok: true }
    end

    # GET /api/users/:id/labels
    def labels
      user = User.find(params[:id])
      labels_hash = user.user_labels.each_with_object({}) do |label, hash|
        hash[label.label_key] = label.gmail_label_id
      end
      render json: labels_hash
    end

    # GET /api/users/:id/emails
    def emails
      user = User.find(params[:id])
      scope = user.emails

      if params[:status].present?
        scope = scope.by_status(params[:status])
      elsif params[:classification].present?
        scope = scope.by_classification(params[:classification])
      else
        scope = scope.pending
      end

      emails = scope.recent.select(
        :id, :gmail_thread_id, :gmail_message_id, :subject,
        :sender_email, :sender_name, :snippet, :classification,
        :status, :confidence, :received_at, :processed_at,
        :drafted_at, :acted_at
      )

      render json: emails
    end
  end
end
