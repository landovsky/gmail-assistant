# frozen_string_literal: true

module Api
  class BaseController < ActionController::Base
    skip_before_action :verify_authenticity_token
    before_action :authenticate!

    rescue_from ActiveRecord::RecordNotFound, with: :not_found
    rescue_from ActiveRecord::RecordInvalid, with: :unprocessable

    private

    def authenticate!
      admin_user = AppConfig.server.admin_user
      admin_password = AppConfig.server.admin_password

      # If no credentials configured, allow all requests
      return if admin_user.blank? || admin_password.blank?

      authenticate_or_request_with_http_basic("Gmail Assistant") do |username, password|
        ActiveSupport::SecurityUtils.secure_compare(username, admin_user) &
          ActiveSupport::SecurityUtils.secure_compare(password, admin_password)
      end
    end

    def not_found(exception)
      render json: { detail: exception.message }, status: :not_found
    end

    def unprocessable(exception)
      render json: { detail: exception.record.errors.full_messages.join(", ") }, status: :unprocessable_entity
    end

    def json_body
      @json_body ||= begin
        JSON.parse(request.body.read).with_indifferent_access
      rescue JSON::ParserError
        {}
      end
    end
  end
end
