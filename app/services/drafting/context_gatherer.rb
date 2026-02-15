# frozen_string_literal: true

module Drafting
  # Gathers related email context to inform draft responses.
  # Uses LLM to generate Gmail search queries, then fetches related threads.
  class ContextGatherer
    MAX_CONTEXT_THREADS = 3
    MAX_QUERIES = 3

    def initialize(user:, gmail_client: nil, llm_gateway: nil)
      @user = user
      @gmail_client = gmail_client || Gmail::Client.new(user: user)
      @llm = llm_gateway || LlmGateway.new
    end

    # Gather related context for an email.
    # Returns a formatted context string or nil if no relevant context found.
    def gather(sender_email:, subject:, body_text:, gmail_thread_id:)
      queries = generate_search_queries(sender_email, subject, body_text)
      return nil if queries.empty?

      threads = fetch_related_threads(queries, exclude_thread_id: gmail_thread_id)
      return nil if threads.empty?

      format_context(threads)
    rescue LlmGateway::LlmError, Gmail::Client::GmailApiError => e
      Rails.logger.warn("Context gathering failed: #{e.message}")
      nil
    end

    private

    def generate_search_queries(sender_email, subject, body_text)
      prompt = <<~PROMPT
        Based on this email, generate up to #{MAX_QUERIES} Gmail search queries to find related conversations in the user's mailbox.
        Focus on finding threads that provide context for writing a reply.

        From: #{sender_email}
        Subject: #{subject}
        Body: #{body_text&.truncate(1000)}

        Return a JSON array of search query strings. Example:
        ["from:#{sender_email} subject:project", "subject:budget Q1", "from:#{sender_email}"]

        Only return the JSON array, nothing else.
      PROMPT

      result = @llm.chat_json(
        model: AppConfig.llm.context_model,
        messages: [{ role: "user", content: prompt }],
        max_tokens: 256,
        temperature: 0.3,
        user: @user,
        call_type: "context"
      )

      queries = result[:parsed_response]
      queries.is_a?(Array) ? queries.first(MAX_QUERIES).select(&:present?) : []
    rescue LlmGateway::LlmError
      # Fallback: simple query by sender
      ["from:#{sender_email}"]
    end

    def fetch_related_threads(queries, exclude_thread_id:)
      seen_thread_ids = Set.new([exclude_thread_id])
      threads = []

      queries.each do |query|
        break if threads.length >= MAX_CONTEXT_THREADS

        begin
          response = @gmail_client.list_messages(query: query, max_results: 5)
          next unless response.messages

          response.messages.each do |msg_ref|
            break if threads.length >= MAX_CONTEXT_THREADS

            message = @gmail_client.get_message(msg_ref.id, format: "metadata")
            thread_id = message.thread_id

            next if seen_thread_ids.include?(thread_id)

            seen_thread_ids.add(thread_id)
            threads << extract_thread_summary(message)
          end
        rescue Gmail::Client::GmailApiError => e
          Rails.logger.debug("Context query failed: #{e.message}")
          next
        end
      end

      threads
    end

    def extract_thread_summary(message)
      parsed = Gmail::MessageParser.parse(message)
      {
        subject: parsed[:subject] || "(no subject)",
        sender: parsed[:sender_email],
        snippet: parsed[:snippet] || message.snippet || ""
      }
    end

    def format_context(threads)
      lines = ["Related context from your mailbox:"]
      threads.each do |thread|
        lines << ""
        lines << "- [Thread: \"#{thread[:subject]}\"]"
        lines << "  From: #{thread[:sender]}"
        lines << "  #{thread[:snippet].truncate(200)}"
      end
      lines.join("\n")
    end
  end
end
