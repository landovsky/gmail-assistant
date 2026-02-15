# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Debug::Emails", type: :request do
  let(:user) { create(:user, email: "debug@example.com") }

  describe "GET /debug/emails" do
    before do
      create(:email, user: user, classification: "needs_response", status: "pending",
                     subject: "Important question")
      create(:email, user: user, classification: "fyi", status: "archived",
                     subject: "Newsletter")
    end

    it "renders the email list page" do
      get "/debug/emails"

      expect(response).to have_http_status(:ok)
      expect(response.body).to include("Email Debug")
      expect(response.body).to include("Important question")
      expect(response.body).to include("Newsletter")
    end

    it "filters by status" do
      get "/debug/emails", params: { status: "archived" }

      expect(response).to have_http_status(:ok)
      expect(response.body).to include("Newsletter")
      expect(response.body).not_to include("Important question")
    end

    it "filters by classification" do
      get "/debug/emails", params: { classification: "needs_response" }

      expect(response).to have_http_status(:ok)
      expect(response.body).to include("Important question")
      expect(response.body).not_to include("Newsletter")
    end

    it "supports search" do
      get "/debug/emails", params: { q: "Newsletter" }

      expect(response).to have_http_status(:ok)
      expect(response.body).to include("Newsletter")
      expect(response.body).not_to include("Important question")
    end

    it "shows empty state when no results" do
      get "/debug/emails", params: { q: "nonexistent" }

      expect(response).to have_http_status(:ok)
      expect(response.body).to include("No emails found")
    end
  end

  describe "GET /debug/email/:id" do
    it "renders the email detail page with timeline" do
      email = create(:email, user: user, classification: "needs_response", status: "pending",
                             subject: "Test Email", reasoning: "Asks a direct question")
      EmailEvent.create!(user: user, gmail_thread_id: email.gmail_thread_id,
                         event_type: "classified", detail: "Classified as needs_response")

      get "/debug/email/#{email.id}"

      expect(response).to have_http_status(:ok)
      expect(response.body).to include("Test Email")
      expect(response.body).to include("Asks a direct question")
      expect(response.body).to include("classified")
      expect(response.body).to include("needs_response")
    end

    it "shows prev/next navigation" do
      email1 = create(:email, user: user)
      email2 = create(:email, user: user)
      email3 = create(:email, user: user)

      get "/debug/email/#{email2.id}"

      expect(response).to have_http_status(:ok)
      expect(response.body).to include("prev")
      expect(response.body).to include("next")
    end

    it "shows empty states for sections with no data" do
      email = create(:email, user: user)

      get "/debug/email/#{email.id}"

      expect(response).to have_http_status(:ok)
      expect(response.body).to include("No timeline entries")
      expect(response.body).to include("No events recorded")
      expect(response.body).to include("No LLM calls recorded")
      expect(response.body).to include("No agent runs recorded")
    end

    it "renders reclassify button" do
      email = create(:email, user: user)

      get "/debug/email/#{email.id}"

      expect(response).to have_http_status(:ok)
      expect(response.body).to include("Reclassify")
      expect(response.body).to include("reclassifyEmail(#{email.id})")
    end
  end
end
