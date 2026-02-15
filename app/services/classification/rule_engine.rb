# frozen_string_literal: true

module Classification
  # Tier 1: Rule-based automation detection.
  # Checks sender patterns, RFC headers, and user blacklists to detect
  # machine-generated emails. Fast, free, runs before LLM.
  class RuleEngine
    # Common automated sender patterns
    AUTOMATED_PATTERNS = %w[
      noreply no-reply do-not-reply donotreply
      mailer-daemon postmaster
      automated notification notifications
      updates alerts news
    ].freeze

    # RFC headers indicating automation
    AUTOMATION_HEADERS = {
      "auto-submitted" => /^auto-/i,
      "precedence" => /^(bulk|list|junk)$/i,
      "list-unsubscribe" => /.+/,
      "list-id" => /.+/,
      "x-auto-response-suppress" => /.+/
    }.freeze

    def initialize(user: nil)
      @user = user
      @blacklist_patterns = load_blacklist_patterns
    end

    # Returns { is_automated: bool, rule_name: string|nil, reasoning: string|nil }
    def evaluate(sender_email:, headers: {})
      # Check 1: User blacklist patterns
      if (pattern = matches_blacklist?(sender_email))
        return automated_result("blacklist_match", "Sender matches blacklist pattern: #{pattern}")
      end

      # Check 2: Automated sender patterns
      if (pattern = matches_automated_pattern?(sender_email))
        return automated_result("automated_sender", "Sender matches automation pattern: #{pattern}")
      end

      # Check 3: RFC automation headers
      if (header_name = has_automation_headers?(headers))
        return automated_result("rfc_header", "Email has automation header: #{header_name}")
      end

      { is_automated: false, rule_name: nil, reasoning: nil }
    end

    private

    def matches_blacklist?(sender_email)
      @blacklist_patterns.find { |pattern| glob_match?(pattern, sender_email) }
    end

    def matches_automated_pattern?(sender_email)
      local_part = sender_email.split("@").first&.downcase || ""
      AUTOMATED_PATTERNS.find { |pattern| local_part.include?(pattern) }
    end

    def has_automation_headers?(headers)
      return nil if headers.blank?

      normalized = headers.transform_keys(&:downcase)
      AUTOMATION_HEADERS.each do |header, pattern|
        value = normalized[header]
        return header if value.present? && value.match?(pattern)
      end
      nil
    end

    def load_blacklist_patterns
      return [] unless @user

      contacts = @user.setting_for("contacts")
      return [] unless contacts.is_a?(Hash)

      Array(contacts["blacklist"])
    end

    def glob_match?(pattern, string)
      # Convert glob pattern to regex: * matches any characters
      regex_str = Regexp.escape(pattern).gsub('\*', '.*')
      string.match?(/\A#{regex_str}\z/i)
    end

    def automated_result(rule_name, reasoning)
      { is_automated: true, rule_name: rule_name, reasoning: reasoning }
    end
  end
end
