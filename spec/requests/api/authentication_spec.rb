# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Api Authentication", type: :request do
  context "when auth credentials are configured" do
    before do
      allow(AppConfig).to receive(:server).and_return(
        OpenStruct.new(
          admin_user: "admin",
          admin_password: "secret123",
          host: "localhost",
          port: 3000,
          log_level: "info",
          worker_concurrency: 3
        )
      )
    end

    it "returns 401 when no credentials provided" do
      get "/api/users"

      expect(response).to have_http_status(:unauthorized)
    end

    it "returns 401 with wrong credentials" do
      get "/api/users",
          headers: { "HTTP_AUTHORIZATION" => ActionController::HttpAuthentication::Basic.encode_credentials("wrong", "creds") }

      expect(response).to have_http_status(:unauthorized)
    end

    it "allows access with correct credentials" do
      get "/api/users",
          headers: { "HTTP_AUTHORIZATION" => ActionController::HttpAuthentication::Basic.encode_credentials("admin", "secret123") }

      expect(response).to have_http_status(:ok)
    end

    it "does not require auth for health endpoint" do
      get "/api/health"
      expect(response).to have_http_status(:ok)
    end

    it "does not require auth for webhook endpoint" do
      data = Base64.encode64({ emailAddress: "test@gmail.com", historyId: 12345 }.to_json)
      post "/webhook/gmail",
           params: { message: { data: data } }.to_json,
           headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:ok)
    end
  end

  context "when auth credentials are not configured" do
    before do
      allow(AppConfig).to receive(:server).and_return(
        OpenStruct.new(
          admin_user: nil,
          admin_password: nil,
          host: "localhost",
          port: 3000,
          log_level: "info",
          worker_concurrency: 3
        )
      )
    end

    it "allows access without credentials" do
      get "/api/users"
      expect(response).to have_http_status(:ok)
    end
  end
end
