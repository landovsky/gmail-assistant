# frozen_string_literal: true

# RubyLLM configuration
# Sets API keys for LLM providers from environment variables

RubyLLM.configure do |config|
  # Gemini API key (primary provider for this app)
  config.gemini_api_key = ENV.fetch("GEMINI_API_KEY", nil)

  # Optional: Other provider API keys
  config.anthropic_api_key = ENV.fetch("ANTHROPIC_API_KEY", nil) if ENV["ANTHROPIC_API_KEY"].present?
  config.openai_api_key = ENV.fetch("OPENAI_API_KEY", nil) if ENV["OPENAI_API_KEY"].present?
end
