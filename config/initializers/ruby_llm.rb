# frozen_string_literal: true

# RubyLLM configuration
# Sets API keys for LLM providers from environment variables

RubyLLM.configure do |config|
  config.gemini_api_key = ENV.fetch('GEMINI_API_KEY', nil)
  config.anthropic_api_key = ENV.fetch('ANTHROPIC_API_KEY', nil)
  config.openai_api_key = ENV.fetch('OPENAI_API_KEY', nil)
end
