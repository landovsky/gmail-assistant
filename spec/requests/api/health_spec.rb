# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Api::Health", type: :request do
  describe "GET /api/health" do
    it "returns ok status" do
      get "/api/health"

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["status"]).to eq("ok")
    end

    it "does not require authentication" do
      # Even with auth configured, health check should be public
      allow(AppConfig).to receive(:server).and_return(
        OpenStruct.new(admin_user: "admin", admin_password: "secret")
      )

      get "/api/health"
      expect(response).to have_http_status(:ok)
    end
  end
end
