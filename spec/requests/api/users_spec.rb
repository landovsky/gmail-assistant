# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Api::Users", type: :request do
  describe "GET /api/users" do
    it "lists active users" do
      user = create(:user, email: "test@example.com", display_name: "Test User")
      create(:user, :inactive, email: "inactive@example.com")

      get "/api/users"

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body.size).to eq(1)
      expect(body.first["email"]).to eq("test@example.com")
      expect(body.first["display_name"]).to eq("Test User")
    end
  end

  describe "POST /api/users" do
    it "creates a new user" do
      post "/api/users",
           params: { email: "new@example.com", display_name: "New User" }.to_json,
           headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["email"]).to eq("new@example.com")
      expect(body["id"]).to be_present
      expect(User.find_by(email: "new@example.com")).to be_present
    end

    it "returns 409 for duplicate email" do
      create(:user, email: "existing@example.com")

      post "/api/users",
           params: { email: "existing@example.com" }.to_json,
           headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:conflict)
      body = JSON.parse(response.body)
      expect(body["detail"]).to eq("User already exists")
    end
  end

  describe "GET /api/users/:id/settings" do
    it "returns user settings as key-value pairs" do
      user = create(:user)
      create(:user_setting, user: user, key: "sign_off_name", value: '"John"')
      create(:user_setting, user: user, key: "default_language", value: '"en"')

      get "/api/users/#{user.id}/settings"

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["sign_off_name"]).to eq("John")
      expect(body["default_language"]).to eq("en")
    end
  end

  describe "PUT /api/users/:id/settings" do
    it "creates a new setting" do
      user = create(:user)

      put "/api/users/#{user.id}/settings",
          params: { key: "sign_off_name", value: "Jane" }.to_json,
          headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["ok"]).to be true

      setting = user.user_settings.find_by(key: "sign_off_name")
      expect(setting.parsed_value).to eq("Jane")
    end

    it "updates an existing setting" do
      user = create(:user)
      create(:user_setting, user: user, key: "lang", value: '"en"')

      put "/api/users/#{user.id}/settings",
          params: { key: "lang", value: "cs" }.to_json,
          headers: { "Content-Type" => "application/json" }

      expect(response).to have_http_status(:ok)
      setting = user.user_settings.find_by(key: "lang")
      expect(setting.parsed_value).to eq("cs")
    end
  end

  describe "GET /api/users/:id/labels" do
    it "returns user labels as key-value pairs" do
      user = create(:user)
      create(:user_label, user: user, label_key: "needs_response", gmail_label_id: "Label_1")
      create(:user_label, user: user, label_key: "fyi", gmail_label_id: "Label_2")

      get "/api/users/#{user.id}/labels"

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["needs_response"]).to eq("Label_1")
      expect(body["fyi"]).to eq("Label_2")
    end
  end

  describe "GET /api/users/:id/emails" do
    let(:user) { create(:user) }

    before do
      create(:email, user: user, classification: "needs_response", status: "pending",
                     subject: "Pending NR")
      create(:email, user: user, classification: "fyi", status: "pending",
                     subject: "Pending FYI")
      create(:email, user: user, classification: "needs_response", status: "drafted",
                     subject: "Drafted NR")
    end

    it "returns pending emails by default" do
      get "/api/users/#{user.id}/emails"

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body.size).to eq(2)
      expect(body.map { |e| e["status"] }).to all(eq("pending"))
    end

    it "filters by status" do
      get "/api/users/#{user.id}/emails", params: { status: "drafted" }

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body.size).to eq(1)
      expect(body.first["subject"]).to eq("Drafted NR")
    end

    it "filters by classification" do
      get "/api/users/#{user.id}/emails", params: { classification: "fyi" }

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body.size).to eq(1)
      expect(body.first["classification"]).to eq("fyi")
    end
  end
end
