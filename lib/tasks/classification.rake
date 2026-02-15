# frozen_string_literal: true

namespace :classification do
  desc "Debug email classification step-by-step. Usage: rake classification:debug[sender@example.com,'Subject line','Body text']"
  task :debug, [:sender_email, :subject, :body] => :environment do |_t, args|
    sender_email = args[:sender_email] || prompt("Sender email: ")
    subject = args[:subject] || prompt("Subject: ")
    body = args[:body] || prompt("Body (enter to finish): ")

    puts colorize("\n=== Classification Debug ===", :cyan)
    puts "Sender: #{sender_email}"
    puts "Subject: #{subject}"
    puts "Body: #{body.truncate(200)}"
    puts ""

    user = User.first
    unless user
      puts colorize("ERROR: No users found. Run OAuth setup first.", :red)
      exit 1
    end

    # Step 1: Rule Engine
    puts colorize("--- Step 1: Rule Engine ---", :yellow)
    rule_engine = Classification::RuleEngine.new(user: user)
    rule_result = rule_engine.evaluate(sender_email: sender_email, headers: {})

    if rule_result[:is_automated]
      puts colorize("  MATCH: #{rule_result[:rule_name]}", :red)
      puts "  Reasoning: #{rule_result[:reasoning]}"
      puts "  Classification: fyi (automated)"
      puts ""
      puts colorize("  Pipeline would stop here (Tier 1 match).", :yellow)
    else
      puts colorize("  No automation detected. Proceeding to Tier 2.", :green)
    end

    puts ""

    # Step 2: LLM Classification prompt preview
    puts colorize("--- Step 2: LLM Classifier ---", :yellow)
    llm_classifier = Classification::LlmClassifier.new
    prompt_preview = build_classification_prompt(sender_email, subject, body)
    puts "  Prompt preview:"
    puts "  #{prompt_preview.truncate(500)}"
    puts ""

    # Step 3: Live LLM call (if API available)
    if ENV["LITELLM_BASE_URL"].present? || ENV["LITELLM_API_KEY"].present?
      puts colorize("  Making live LLM call...", :yellow)
      begin
        result = llm_classifier.classify(
          sender_email: sender_email,
          sender_name: sender_email.split("@").first,
          subject: subject,
          body_text: body,
          user: user
        )
        puts colorize("  Category: #{result[:category]}", classification_color(result[:category]))
        puts "  Confidence: #{result[:confidence]}"
        puts "  Style: #{result[:communication_style]}"
        puts "  Language: #{result[:detected_language]}"
        puts "  Reasoning: #{result[:reasoning]}"
      rescue LlmGateway::LlmError => e
        puts colorize("  LLM call failed: #{e.message}", :red)
      end
    else
      puts colorize("  Skipping live LLM call (no LITELLM_BASE_URL set).", :yellow)
    end

    # Step 4: Style resolution
    puts ""
    puts colorize("--- Step 3: Style Resolution ---", :yellow)
    contacts = user.setting_for("contacts")
    if contacts.is_a?(Hash) && contacts["style_overrides"]&.key?(sender_email)
      puts "  Override found: #{contacts['style_overrides'][sender_email]}"
    else
      puts "  No override. Will use LLM-detected style."
    end

    puts ""
    puts colorize("=== Debug Complete ===", :cyan)
  end

  desc "Run classification test suite against fixtures. Usage: rake classification:test[path/to/fixtures.yml]"
  task :test, [:fixture_file] => :environment do |_t, args|
    fixture_file = args[:fixture_file] || "config/classification_fixtures.yml"
    unless File.exist?(fixture_file)
      puts colorize("Fixture file not found: #{fixture_file}", :red)
      puts "Create a YAML file with test cases:"
      puts "  - sender_email: noreply@example.com"
      puts "    subject: Order shipped"
      puts "    body: Your order #123 has shipped"
      puts "    expected_category: fyi"
      puts "    expected_tier: rules"
      exit 1
    end

    fixtures = YAML.safe_load(File.read(fixture_file), permitted_classes: [Symbol])
    unless fixtures.is_a?(Array)
      puts colorize("Fixture file must contain an array of test cases.", :red)
      exit 1
    end

    user = User.first
    unless user
      puts colorize("ERROR: No users found.", :red)
      exit 1
    end

    rule_engine = Classification::RuleEngine.new(user: user)
    passed = 0
    failed = 0
    confusion = Hash.new { |h, k| h[k] = Hash.new(0) }

    puts colorize("Running #{fixtures.size} classification test cases...\n", :cyan)

    fixtures.each_with_index do |tc, i|
      sender = tc["sender_email"]
      subject = tc["subject"]
      expected = tc["expected_category"]
      expected_tier = tc["expected_tier"]

      # Run rule engine
      rule_result = rule_engine.evaluate(sender_email: sender, headers: tc["headers"] || {})

      if rule_result[:is_automated]
        actual_category = "fyi"
        actual_tier = "rules"
      else
        actual_category = "unknown"
        actual_tier = "llm"
      end

      # Only run LLM if needed and available
      if actual_tier == "llm" && (ENV["LITELLM_BASE_URL"].present? || ENV["LITELLM_API_KEY"].present?)
        begin
          llm_classifier = Classification::LlmClassifier.new
          result = llm_classifier.classify(
            sender_email: sender,
            sender_name: sender.split("@").first,
            subject: subject,
            body_text: tc["body"],
            user: user
          )
          actual_category = result[:category]
        rescue LlmGateway::LlmError
          actual_category = "error"
        end
      end

      # Check result
      category_match = actual_category == expected
      tier_match = expected_tier.nil? || actual_tier == expected_tier
      pass = category_match && tier_match

      if pass
        passed += 1
        puts colorize("  PASS", :green) + " [#{i + 1}] #{subject} → #{actual_category} (#{actual_tier})"
      else
        failed += 1
        puts colorize("  FAIL", :red) + " [#{i + 1}] #{subject}"
        puts "       Expected: #{expected} (#{expected_tier || 'any'})"
        puts "       Actual:   #{actual_category} (#{actual_tier})"
        confusion[expected][actual_category] += 1
      end
    end

    puts ""
    total = passed + failed
    accuracy = total > 0 ? (passed.to_f / total * 100).round(1) : 0
    color = failed.zero? ? :green : :red
    puts colorize("Results: #{passed}/#{total} passed (#{accuracy}% accuracy)", color)

    if confusion.any?
      puts ""
      puts colorize("Confusion Matrix (expected → actual):", :yellow)
      confusion.each do |expected, actuals|
        actuals.each do |actual, count|
          puts "  #{expected} → #{actual}: #{count}"
        end
      end
    end

    exit(failed.zero? ? 0 : 1)
  end
end

def prompt(message)
  print message
  $stdin.gets&.chomp || ""
end

def build_classification_prompt(sender_email, subject, body)
  <<~PROMPT
    Classify this email into one of: needs_response, action_required, payment_request, fyi, waiting
    From: #{sender_email}
    Subject: #{subject}
    Body: #{body&.truncate(500)}
  PROMPT
end

def colorize(text, color)
  colors = { red: 31, green: 32, yellow: 33, cyan: 36 }
  code = colors[color] || 0
  "\e[#{code}m#{text}\e[0m"
end

def classification_color(category)
  case category
  when "needs_response" then :red
  when "action_required" then :yellow
  when "payment_request" then :yellow
  when "fyi" then :green
  when "waiting" then :cyan
  else :red
  end
end
