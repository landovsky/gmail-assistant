# frozen_string_literal: true

module Agent
  # Evaluates routing rules to determine whether an email goes to the standard
  # classification pipeline or an agent profile.
  class Router
    RouteDecision = Struct.new(:route, :profile, :rule_name, :metadata, keyword_init: true)

    def initialize(rules: nil)
      @rules = rules || AppConfig.routing.fetch("rules", [])
    end

    # Evaluate email against routing rules. Returns a RouteDecision.
    # email_data keys: sender_email, subject, headers (hash), body
    def route(email_data)
      email_data = email_data.with_indifferent_access

      @rules.each do |rule|
        match_criteria = rule["match"] || {}
        next unless matches?(match_criteria, email_data)

        return RouteDecision.new(
          route: rule.fetch("route", "pipeline"),
          profile: rule["profile"],
          rule_name: rule["name"],
          metadata: rule.except("name", "match", "route", "profile")
        )
      end

      # Default: pipeline
      RouteDecision.new(route: "pipeline", profile: nil, rule_name: "default_fallback", metadata: {})
    end

    private

    def matches?(criteria, email_data)
      criteria.all? do |key, value|
        case key.to_s
        when "all"
          value == true
        when "forwarded_from"
          match_forwarded_from(value, email_data)
        when "sender_domain"
          match_sender_domain(value, email_data)
        when "sender_email"
          email_data[:sender_email]&.downcase == value.downcase
        when "subject_contains"
          email_data[:subject]&.downcase&.include?(value.downcase)
        when "header_match"
          match_headers(value, email_data)
        else
          false
        end
      end
    end

    def match_forwarded_from(forwarder, email_data)
      forwarder = forwarder.downcase

      # Check sender
      return true if email_data[:sender_email]&.downcase == forwarder

      headers = email_data[:headers] || {}

      # Check X-Forwarded-From header
      return true if headers["X-Forwarded-From"]&.downcase&.include?(forwarder)

      # Check Reply-To header
      return true if headers["Reply-To"]&.downcase&.include?(forwarder)

      # Check body for forwarding patterns
      body = email_data[:body] || ""
      body_patterns = [/From:\s*.*#{Regexp.escape(forwarder)}/i, /Od:\s*.*#{Regexp.escape(forwarder)}/i]
      body_patterns.any? { |pattern| body.match?(pattern) }
    end

    def match_sender_domain(domain, email_data)
      sender = email_data[:sender_email] || ""
      sender_domain = sender.split("@").last
      sender_domain&.downcase == domain.downcase
    end

    def match_headers(header_criteria, email_data)
      headers = email_data[:headers] || {}
      header_criteria.all? do |header_name, pattern|
        value = headers[header_name]
        value && value.match?(Regexp.new(pattern))
      end
    end
  end
end
