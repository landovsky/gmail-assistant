# frozen_string_literal: true

module Api
  class HealthController < BaseController
    skip_before_action :authenticate!

    # GET /api/health
    def show
      render json: { status: "ok" }
    end
  end
end
