# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Api::Sync", type: :request do
  describe "POST /api/sync" do
    let!(:user) { create(:user) }

    it "enqueues a sync job for the default user" do
      post "/api/sync", params: { user_id: user.id }.to_json,
                        headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["queued"]).to be true
      expect(body["user_id"]).to eq(user.id)
      expect(body["full"]).to be false
    end

    it "forces full sync when full=true" do
      user.sync_state.update!(last_history_id: "12345")

      post "/api/sync", params: { user_id: user.id, full: "true" }.to_json,
                        headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["full"]).to be true
      expect(user.sync_state.reload.last_history_id).to eq("0")
    end

    it "returns 404 for unknown user" do
      post "/api/sync", params: { user_id: 999 }.to_json,
                        headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:not_found)
      body = JSON.parse(response.body)
      expect(body["detail"]).to include("not found")
    end
  end
end
