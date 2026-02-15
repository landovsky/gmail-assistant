# frozen_string_literal: true

# Loads application configuration from config/app.yml with environment variable overrides.
# Environment variables use the GMA_ prefix and follow the pattern GMA_SECTION_KEY.
# Example: GMA_LLM_CLASSIFY_MODEL overrides llm.classify_model in the YAML.
class AppConfig
  class << self
    def instance
      @instance ||= new
    end

    delegate :get, :llm, :sync, :server, :auth, :routing, to: :instance

    def reload!
      @instance = nil
    end
  end

  def initialize
    @config = load_config
  end

  def get(section, key, default: nil)
    section_data = @config.dig(section.to_s)
    return default unless section_data

    env_key = "GMA_#{section.to_s.upcase}_#{key.to_s.upcase}"
    env_val = ENV[env_key]
    return cast_value(env_val, default) if env_val.present?

    section_data.fetch(key.to_s, default)
  end

  def llm
    @llm ||= OpenStruct.new(
      classify_model: get(:llm, :classify_model, default: "gemini/gemini-2.0-flash"),
      draft_model: get(:llm, :draft_model, default: "gemini/gemini-2.5-pro"),
      context_model: get(:llm, :context_model, default: "gemini/gemini-2.0-flash"),
      max_classify_tokens: get(:llm, :max_classify_tokens, default: 256).to_i,
      max_draft_tokens: get(:llm, :max_draft_tokens, default: 2048).to_i
    )
  end

  def sync
    @sync ||= OpenStruct.new(
      fallback_interval_minutes: get(:sync, :fallback_interval_minutes, default: 15).to_i,
      full_sync_interval_hours: get(:sync, :full_sync_interval_hours, default: 1).to_i,
      history_max_results: get(:sync, :history_max_results, default: 100).to_i
    )
  end

  def server
    @server ||= OpenStruct.new(
      host: get(:server, :host, default: "localhost"),
      port: get(:server, :port, default: 3000).to_i,
      log_level: get(:server, :log_level, default: "info"),
      worker_concurrency: get(:server, :worker_concurrency, default: 3).to_i,
      admin_user: ENV.fetch("GMA_SERVER_ADMIN_USER", nil),
      admin_password: ENV.fetch("GMA_SERVER_ADMIN_PASSWORD", nil)
    )
  end

  def auth
    @auth ||= OpenStruct.new(
      mode: get(:auth, :mode, default: "personal_oauth"),
      credentials_file: get(:auth, :credentials_file, default: "config/credentials.json"),
      token_file: get(:auth, :token_file, default: "config/token.json"),
      scopes: @config.dig("auth", "scopes") || ["https://www.googleapis.com/auth/gmail.modify"]
    )
  end

  def routing
    @routing ||= @config.dig("routing") || { "rules" => [{ "name" => "default", "match" => { "all" => true }, "route" => "pipeline" }] }
  end

  private

  def load_config
    config_path = Rails.root.join("config", "app.yml")
    return {} unless File.exist?(config_path)

    YAML.safe_load(File.read(config_path), aliases: true) || {}
  rescue Psych::SyntaxError => e
    Rails.logger.error("Failed to parse config/app.yml: #{e.message}")
    {}
  end

  def cast_value(env_val, default)
    case default
    when Integer
      env_val.to_i
    when Float
      env_val.to_f
    when TrueClass, FalseClass
      %w[true 1 yes].include?(env_val.downcase)
    else
      env_val
    end
  end
end
