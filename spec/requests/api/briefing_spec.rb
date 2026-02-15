# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Api::Briefing", type: :request do
  describe "GET /api/briefing/:user_email" do
    let(:user) { create(:user, email: "me@example.com") }

    before do
      create(:email, user: user, classification: "needs_response", status: "pending")
      create(:email, user: user, classification: "needs_response", status: "drafted")
      create(:email, user: user, classification: "needs_response", status: "sent")
      create(:email, user: user, classification: "action_required", status: "pending")
      create(:email, user: user, classification: "fyi", status: "archived")
      create(:email, user: user, classification: "payment_request", status: "pending")
      create(:email, user: user, classification: "waiting", status: "pending")
    end

    it "returns inbox briefing summary" do
      get "/api/briefing/#{user.email}"

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)

      expect(body["user"]).to eq("me@example.com")
      expect(body["summary"]["needs_response"]["total"]).to eq(3)
      expect(body["summary"]["needs_response"]["active"]).to eq(2) # pending + drafted
      expect(body["summary"]["action_required"]["total"]).to eq(1)
      expect(body["summary"]["action_required"]["active"]).to eq(1)
      expect(body["summary"]["fyi"]["total"]).to eq(1)
      expect(body["summary"]["fyi"]["active"]).to eq(0) # archived
      expect(body["pending_drafts"]).to eq(1) # needs_response + pending
      expect(body["action_items"]).to eq(3) # active NR (2) + active AR (1)
    end

    it "returns 404 for unknown user" do
      get "/api/briefing/unknown@example.com"

      expect(response).to have_http_status(:not_found)
    end
  end
end
