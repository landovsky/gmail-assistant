# frozen_string_literal: true

namespace :context do
  desc "Debug context gathering for an email. Usage: rake context:debug[sender@example.com,'Subject','Body text']"
  task :debug, [:sender_email, :subject, :body] => :environment do |_t, args|
    sender_email = args[:sender_email]
    subject = args[:subject]
    body = args[:body]

    unless sender_email && subject
      puts "\e[31mUsage: rake context:debug[sender@example.com,'Subject line','Body text']\e[0m"
      exit 1
    end

    user = User.first
    unless user
      puts "\e[31mERROR: No users found. Run OAuth setup first.\e[0m"
      exit 1
    end

    puts "\e[36m=== Context Gathering Debug ===\e[0m"
    puts "Sender: #{sender_email}"
    puts "Subject: #{subject}"
    puts "Body: #{body&.truncate(200)}"
    puts ""

    # Step 1: Generate search queries
    puts "\e[33m--- Step 1: LLM Search Query Generation ---\e[0m"

    if ENV["LITELLM_BASE_URL"].blank? && ENV["LITELLM_API_KEY"].blank?
      puts "\e[33m  Skipping LLM call (no LITELLM_BASE_URL set).\e[0m"
      puts "  Fallback query: from:#{sender_email}"
      puts ""
      puts "\e[33m--- Step 2: Gmail Search (requires live API) ---\e[0m"
      puts "\e[33m  Skipping Gmail search (no live API).\e[0m"
      puts ""
      puts "\e[36m=== Debug Complete ===\e[0m"
      exit 0
    end

    llm = LlmGateway.new
    prompt = <<~PROMPT
      Based on this email, generate up to 3 Gmail search queries to find related conversations.
      Focus on finding threads that provide context for writing a reply.

      From: #{sender_email}
      Subject: #{subject}
      Body: #{body&.truncate(1000)}

      Return a JSON array of search query strings.
    PROMPT

    begin
      result = llm.chat_json(
        model: AppConfig.llm.context_model,
        messages: [{ role: "user", content: prompt }],
        max_tokens: 256,
        temperature: 0.3,
        user: user,
        call_type: "context_debug"
      )

      queries = result[:parsed_response]
      puts "  Raw LLM response: #{result[:response_text]}"
      puts "  Parsed queries:"
      if queries.is_a?(Array)
        queries.each_with_index do |q, i|
          puts "    #{i + 1}. #{q}"
        end
      else
        puts "\e[31m  Invalid response format: #{queries.class}\e[0m"
      end
    rescue LlmGateway::LlmError => e
      puts "\e[31m  LLM call failed: #{e.message}\e[0m"
      queries = ["from:#{sender_email}"]
      puts "  Fallback query: #{queries.first}"
    end

    # Step 2: Execute queries against Gmail (if available)
    puts ""
    puts "\e[33m--- Step 2: Gmail Search ---\e[0m"
    begin
      gmail_client = Gmail::Client.new(user: user)
      seen = Set.new
      threads = []

      queries.each do |query|
        break if threads.length >= 3

        puts "  Executing: #{query}"
        response = gmail_client.list_messages(query: query, max_results: 5)
        unless response.messages
          puts "    No results."
          next
        end

        response.messages.each do |msg_ref|
          break if threads.length >= 3

          message = gmail_client.get_message(msg_ref.id, format: "metadata")
          thread_id = message.thread_id
          next if seen.include?(thread_id)

          seen.add(thread_id)
          parsed = Gmail::MessageParser.parse(message)
          threads << parsed
          puts "    Found: #{parsed[:subject]} (from: #{parsed[:sender_email]})"
        end
      end

      if threads.any?
        puts ""
        puts "\e[33m--- Step 3: Formatted Context Block ---\e[0m"
        context_lines = ["Related context from your mailbox:"]
        threads.each do |t|
          context_lines << ""
          context_lines << "- [Thread: \"#{t[:subject]}\"]"
          context_lines << "  From: #{t[:sender_email]}"
          context_lines << "  #{t[:snippet]&.truncate(200)}"
        end
        puts context_lines.join("\n")
      else
        puts "  No related threads found."
      end
    rescue Gmail::Client::GmailApiError => e
      puts "\e[31m  Gmail API error: #{e.message}\e[0m"
      puts "  Context gathering requires live Gmail API access."
    rescue StandardError => e
      puts "\e[31m  Error: #{e.message}\e[0m"
    end

    puts ""
    puts "\e[36m=== Debug Complete ===\e[0m"
  end
end
