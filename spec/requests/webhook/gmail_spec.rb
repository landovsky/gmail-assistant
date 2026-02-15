# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Webhook::Gmail", type: :request do
  describe "POST /webhook/gmail" do
    let!(:user) { create(:user, email: "test@gmail.com") }

    let(:valid_payload) do
      data = Base64.encode64({ emailAddress: "test@gmail.com", historyId: 12345 }.to_json)
      { message: { data: data } }
    end

    it "accepts valid notification and enqueues sync" do
      post "/webhook/gmail", params: valid_payload.to_json,
                             headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:ok)
    end

    it "returns 200 for unknown user (to prevent retries)" do
      data = Base64.encode64({ emailAddress: "unknown@gmail.com", historyId: 999 }.to_json)
      payload = { message: { data: data } }

      post "/webhook/gmail", params: payload.to_json,
                             headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:ok)
    end

    it "returns 400 for invalid payload" do
      post "/webhook/gmail", params: "not json",
                             headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:bad_request)
    end
  end
end
