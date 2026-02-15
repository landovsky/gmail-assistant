# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Api::Debug", type: :request do
  let(:user) { create(:user, email: "debug@example.com") }

  describe "GET /api/debug/emails" do
    before do
      create(:email, user: user, classification: "needs_response", status: "pending",
                     subject: "Invoice from vendor", sender_email: "billing@vendor.com")
      create(:email, user: user, classification: "fyi", status: "archived",
                     subject: "Newsletter update")
      create(:email, user: user, classification: "action_required", status: "pending",
                     subject: "Please review document")
    end

    it "returns all emails by default (newest first)" do
      get "/api/debug/emails"

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["count"]).to eq(3)
      expect(body["limit"]).to eq(50)
      # Newest first (highest ID first)
      ids = body["emails"].map { |e| e["id"] }
      expect(ids).to eq(ids.sort.reverse)
    end

    it "filters by status" do
      get "/api/debug/emails", params: { status: "archived" }

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["count"]).to eq(1)
      expect(body["filters"]["status"]).to eq("archived")
    end

    it "filters by classification" do
      get "/api/debug/emails", params: { classification: "needs_response" }

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["count"]).to eq(1)
      expect(body["emails"].first["classification"]).to eq("needs_response")
    end

    it "supports full-text search" do
      get "/api/debug/emails", params: { q: "Invoice" }

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["count"]).to eq(1)
      expect(body["emails"].first["subject"]).to include("Invoice")
    end

    it "respects limit parameter" do
      get "/api/debug/emails", params: { limit: 1 }

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["count"]).to eq(1)
      expect(body["limit"]).to eq(1)
    end

    it "includes debug counts" do
      email = Email.last
      EmailEvent.create!(user: user, gmail_thread_id: email.gmail_thread_id,
                         event_type: "classified", detail: "test")

      get "/api/debug/emails"

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      matching = body["emails"].find { |e| e["id"] == email.id }
      expect(matching["event_count"]).to eq(1)
    end
  end

  describe "GET /api/emails/:id/debug" do
    it "returns full debug data for an email" do
      email = create(:email, user: user, classification: "needs_response", status: "pending")
      EmailEvent.create!(user: user, gmail_thread_id: email.gmail_thread_id,
                         event_type: "classified", detail: "Test classification")
      LlmCall.log_call(
        call_type: "classify",
        model: "test-model",
        user: user,
        gmail_thread_id: email.gmail_thread_id,
        prompt_tokens: 100,
        completion_tokens: 50,
        latency_ms: 200
      )

      get "/api/emails/#{email.id}/debug"

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)

      expect(body["email"]["id"]).to eq(email.id)
      expect(body["events"].size).to eq(1)
      expect(body["llm_calls"].size).to eq(1)
      expect(body["timeline"].size).to eq(2) # 1 event + 1 llm call
      expect(body["summary"]["event_count"]).to eq(1)
      expect(body["summary"]["llm_call_count"]).to eq(1)
      expect(body["summary"]["total_tokens"]).to eq(150)
      expect(body["summary"]["total_latency_ms"]).to eq(200)
      expect(body["summary"]["llm_breakdown"]["classify"]["count"]).to eq(1)
    end

    it "returns 404 for unknown email" do
      get "/api/emails/999/debug"

      expect(response).to have_http_status(:not_found)
    end
  end
end
