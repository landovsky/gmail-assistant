# frozen_string_literal: true

require "rails_helper"

RSpec.describe "API Contract", type: :request do
  let(:user) { create(:user) }
  let(:auth_header) { "Basic #{Base64.strict_encode64('admin:password')}" }

  before do
    allow(AppConfig).to receive_message_chain(:server, :admin_user).and_return("admin")
    allow(AppConfig).to receive_message_chain(:server, :admin_password).and_return("password")
  end

  describe "GET /api/health" do
    it "returns status ok without auth" do
      get "/api/health"
      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body)["status"]).to eq("ok")
    end
  end

  describe "GET /api/users/:id/emails" do
    it "returns filtered emails with expected fields" do
      5.times do |i|
        create(:email, user: user,
               gmail_thread_id: "thread_api_#{i}",
               gmail_message_id: "msg_api_#{i}",
               status: "pending")
      end

      get "/api/users/#{user.id}/emails",
          params: { status: "pending" },
          headers: { "Authorization" => auth_header }

      expect(response).to have_http_status(:ok)
      data = JSON.parse(response.body)
      expect(data).to be_an(Array)
      expect(data.size).to eq(5)
      expect(data.first).to include("gmail_thread_id", "subject", "classification", "status")
    end
  end

  describe "POST /api/sync" do
    it "enqueues sync job with full flag" do
      # User factory already creates sync_state, just update it
      user.sync_state.update!(last_history_id: "12345")

      post "/api/sync",
           params: { user_id: user.id, full: "true" },
           headers: { "Authorization" => auth_header }

      expect(response).to have_http_status(:ok)
      data = JSON.parse(response.body)
      expect(data["queued"]).to be true
    end
  end

  describe "GET /api/emails/:id/debug" do
    it "returns complete debug data for an email" do
      email = create(:email, user: user)
      EmailEvent.create!(user: user, gmail_thread_id: email.gmail_thread_id,
                         event_type: "classified", detail: "Test classification")

      get "/api/emails/#{email.id}/debug",
          headers: { "Authorization" => auth_header }

      expect(response).to have_http_status(:ok)
      data = JSON.parse(response.body)
      expect(data).to include("email", "events", "timeline")
    end
  end

  describe "POST /api/emails/:id/reclassify" do
    it "enqueues reclassification job" do
      email = create(:email, user: user, classification: "fyi")

      post "/api/emails/#{email.id}/reclassify",
           headers: { "Authorization" => auth_header }

      expect(response).to have_http_status(:ok)
      data = JSON.parse(response.body)
      expect(data["status"]).to eq("queued")
    end
  end

  describe "POST /api/reset" do
    it "deletes transient data and returns counts" do
      email = create(:email, user: user)
      EmailEvent.create!(user: user, gmail_thread_id: email.gmail_thread_id, event_type: "classified")

      post "/api/reset",
           headers: { "Authorization" => auth_header }

      expect(response).to have_http_status(:ok)
      data = JSON.parse(response.body)
      expect(data["deleted"]).to be_a(Hash)
      expect(Email.count).to eq(0)
      expect(EmailEvent.count).to eq(0)
    end
  end

  describe "POST /webhook/gmail" do
    it "accepts valid Pub/Sub notification and enqueues sync" do
      notification_data = { emailAddress: user.email, historyId: 99999 }
      encoded = Base64.strict_encode64(notification_data.to_json)

      post "/webhook/gmail",
           params: { message: { data: encoded } },
           as: :json

      expect(response).to have_http_status(:ok)
    end
  end

  describe "GET /api/briefing/:user_email" do
    it "returns inbox summary" do
      create(:email, user: user, classification: "needs_response", status: "pending")
      create(:email, user: user, classification: "fyi", status: "pending",
             gmail_thread_id: "t2", gmail_message_id: "m2")
      create(:email, user: user, classification: "fyi", status: "pending",
             gmail_thread_id: "t3", gmail_message_id: "m3")

      get "/api/briefing/#{user.email}",
          headers: { "Authorization" => auth_header }

      expect(response).to have_http_status(:ok)
      data = JSON.parse(response.body)
      expect(data["user"]).to eq(user.email)
      expect(data["summary"]).to be_a(Hash)
      expect(data["summary"]).to include("needs_response", "fyi")
    end
  end

  describe "authentication requirement" do
    it "rejects unauthenticated requests to protected endpoints" do
      get "/api/users"
      expect(response).to have_http_status(:unauthorized)
    end

    it "accepts authenticated requests" do
      get "/api/users",
          headers: { "Authorization" => auth_header }
      expect(response).to have_http_status(:ok)
    end

    it "allows health check without auth" do
      get "/api/health"
      expect(response).to have_http_status(:ok)
    end
  end
end
