# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Api::Emails", type: :request do
  describe "POST /api/emails/:id/reclassify" do
    let(:user) { create(:user) }

    it "enqueues a reclassification job" do
      email = create(:email, user: user, classification: "fyi", status: "pending")

      post "/api/emails/#{email.id}/reclassify"

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["status"]).to eq("queued")
      expect(body["email_id"]).to eq(email.id)
      expect(body["current_classification"]).to eq("fyi")
      expect(body["job_id"]).to be_present
    end

    it "returns 400 when email has no gmail_message_id" do
      email = create(:email, user: user)
      # Simulate missing gmail_message_id by stubbing the check
      allow_any_instance_of(Email).to receive(:gmail_message_id).and_return(nil)

      post "/api/emails/#{email.id}/reclassify"

      expect(response).to have_http_status(:bad_request)
      body = JSON.parse(response.body)
      expect(body["detail"]).to include("Gmail message ID")
    end

    it "returns 404 for unknown email" do
      post "/api/emails/999/reclassify"

      expect(response).to have_http_status(:not_found)
    end
  end
end
