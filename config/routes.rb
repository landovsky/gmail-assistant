# frozen_string_literal: true

Rails.application.routes.draw do
  # Health check (public)
  get "api/health", to: "api/health#show"

  # Root redirects to debug emails
  root to: redirect("/debug/emails")

  # API routes
  namespace :api do
    # User management
    resources :users, only: %i[index create] do
      member do
        get :settings
        put :settings, action: :update_settings
        get :labels
        get :emails
      end
    end

    # Authentication & onboarding
    post "auth/init", to: "auth#init"

    # Gmail watch management
    post "watch", to: "watch#create"
    get "watch/status", to: "watch#status"

    # Sync operations
    post "sync", to: "sync#create"
    post "reset", to: "reset#create"

    # Briefing
    get "briefing/:user_email", to: "briefing#show", constraints: { user_email: /[^\/]+/ }

    # Debug endpoints (JSON)
    get "debug/emails", to: "debug#emails"
    get "emails/:id/debug", to: "debug#show"
    post "emails/:id/reclassify", to: "emails#reclassify"
  end

  # Webhook (public, no auth)
  post "webhook/gmail", to: "webhook/gmail#create"

  # Debug HTML interface
  get "debug/emails", to: "debug/emails#index", as: :debug_emails
  get "debug/email/:id", to: "debug/emails#show", as: :debug_email

  # Rails health check
  get "up" => "rails/health#show", as: :rails_health_check
end
