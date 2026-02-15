# frozen_string_literal: true

module Classification
  # Tier 2: LLM-based email classification.
  # Sends email content to LLM for intelligent categorization.
  class LlmClassifier
    CLASSIFICATION_PROMPT = <<~PROMPT
      You are an email classification assistant. Analyze the email and classify it into exactly one category.

      Categories:
      - needs_response: Direct questions or requests requiring a reply from the user
      - action_required: Meeting requests, task assignments, approvals (no email reply needed)
      - payment_request: Unpaid invoices or bills with amount due (NOT receipts or payment confirmations)
      - fyi: Newsletters, notifications, informational emails (no action needed)
      - waiting: The user sent the last message and is waiting for a reply

      Also determine:
      - communication_style: formal | business | informal (based on sender's writing style)
      - detected_language: ISO 639-1 language code (e.g., cs, en, de)
      - confidence: high | medium | low
      - reasoning: Brief explanation of your classification decision
      - vendor_name: If payment_request, extract the vendor/company name (null otherwise)

      Respond with valid JSON only:
      {
        "category": "needs_response|action_required|payment_request|fyi|waiting",
        "communication_style": "formal|business|informal",
        "detected_language": "cs",
        "confidence": "high|medium|low",
        "reasoning": "explanation",
        "vendor_name": null
      }
    PROMPT

    def initialize(llm_gateway: nil)
      @llm = llm_gateway || LlmGateway.new
      @config = AppConfig.llm
    end

    # Classify an email using LLM.
    # Returns { category:, communication_style:, detected_language:, confidence:, reasoning:, vendor_name: }
    def classify(sender_email:, sender_name: nil, subject: nil, body_text: nil,
                 thread_context: nil, user: nil, gmail_thread_id: nil)
      user_message = build_user_message(
        sender_email: sender_email,
        sender_name: sender_name,
        subject: subject,
        body_text: body_text,
        thread_context: thread_context
      )

      result = @llm.chat_json(
        model: @config.classify_model,
        messages: [
          { role: "system", content: CLASSIFICATION_PROMPT },
          { role: "user", content: user_message }
        ],
        max_tokens: @config.max_classify_tokens,
        temperature: 0.0,
        user: user,
        gmail_thread_id: gmail_thread_id,
        call_type: "classify"
      )

      normalize_result(result[:parsed_response])
    end

    private

    def build_user_message(sender_email:, sender_name:, subject:, body_text:, thread_context:)
      parts = []
      parts << "From: #{sender_name} <#{sender_email}>" if sender_name
      parts << "From: #{sender_email}" unless sender_name
      parts << "Subject: #{subject}" if subject
      parts << ""
      parts << "Email body:"
      parts << (body_text.present? ? truncate_body(body_text) : "(empty)")

      if thread_context.present?
        parts << ""
        parts << "Thread context (previous messages):"
        parts << thread_context
      end

      parts.join("\n")
    end

    def truncate_body(body_text, max_chars: 4000)
      return body_text if body_text.length <= max_chars

      body_text[0...max_chars] + "\n...(truncated)"
    end

    def normalize_result(parsed)
      category = parsed["category"]&.downcase
      category = "fyi" unless Email::CLASSIFICATIONS.include?(category)

      confidence = parsed["confidence"]&.downcase
      confidence = "medium" unless Email::CONFIDENCES.include?(confidence)

      style = parsed["communication_style"]&.downcase
      style = "business" unless %w[formal business informal].include?(style)

      language = parsed["detected_language"]&.downcase || "cs"

      {
        category: category,
        communication_style: style,
        detected_language: language,
        confidence: confidence,
        reasoning: parsed["reasoning"] || "",
        vendor_name: parsed["vendor_name"]
      }
    end
  end
end
