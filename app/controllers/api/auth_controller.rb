# frozen_string_literal: true

module Api
  class AuthController < BaseController
    # POST /api/auth/init
    # Bootstrap OAuth and onboard the first user.
    def init
      display_name = params[:display_name]
      migrate_v1 = params[:migrate_v1] != "false"

      # Validate credentials file exists
      credentials_path = Rails.root.join(AppConfig.auth.credentials_file)
      unless File.exist?(credentials_path)
        render json: { detail: "credentials.json not found at #{credentials_path}" }, status: :bad_request
        return
      end

      # Create Gmail client and get user email from profile
      begin
        gmail_client = Gmail::Client.new(credentials_path: credentials_path.to_s)
        profile = gmail_client.get_profile
        user_email = profile.email_address
      rescue StandardError => e
        render json: { detail: "Could not get email from Gmail profile: #{e.message}" }, status: :internal_server_error
        return
      end

      unless user_email.present?
        render json: { detail: "Could not get email from Gmail profile" }, status: :internal_server_error
        return
      end

      # Create or find user
      user = User.find_or_create_by!(email: user_email) do |u|
        u.display_name = display_name || user_email.split("@").first
      end

      # Provision Gmail labels
      label_manager = Gmail::LabelManager.new(user: user, gmail_client: gmail_client)
      migrated = false

      if migrate_v1
        label_ids_path = Rails.root.join("config", "label_ids.yml")
        if File.exist?(label_ids_path)
          label_ids = YAML.safe_load(File.read(label_ids_path)) || {}
          label_ids.each do |key, gmail_id|
            user.user_labels.find_or_create_by!(label_key: key) do |label|
              label.gmail_label_id = gmail_id
            end
          end
          migrated = true
        end
      end

      # Create labels if not migrated
      unless migrated
        label_manager.ensure_labels!
      end

      # Initialize sync state with current history ID
      begin
        history_id = profile.history_id.to_s
        user.sync_state.update_history_id!(history_id)
      rescue StandardError => e
        Rails.logger.warn("Could not set initial history ID: #{e.message}")
      end

      # Mark as onboarded
      user.update!(onboarded_at: Time.current) unless user.onboarded_at.present?

      render json: {
        user_id: user.id,
        email: user.email,
        onboarded: true,
        migrated_v1: migrated
      }
    end
  end
end
