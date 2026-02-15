# frozen_string_literal: true

module Classification
  # Orchestrates the two-tier classification pipeline:
  # 1. Rule engine checks for automation
  # 2. LLM classifies (if not automated)
  # 3. Safety net override
  # 4. Style/language resolution
  # 5. Store results and apply labels
  class Pipeline
    def initialize(user:, gmail_client: nil, llm_gateway: nil)
      @user = user
      @rule_engine = RuleEngine.new(user: user)
      @llm_classifier = LlmClassifier.new(llm_gateway: llm_gateway)
      @label_manager = Gmail::LabelManager.new(user: user, gmail_client: gmail_client)
    end

    # Process a new email through the classification pipeline.
    # Returns the created/updated Email record.
    def classify(email_data:, headers: {}, thread_context: nil, force: false)
      # Step 1: Rule-based automation detection
      rule_result = @rule_engine.evaluate(
        sender_email: email_data[:sender_email],
        headers: headers
      )

      if rule_result[:is_automated] && !force
        return classify_as_automated(email_data, rule_result)
      end

      # Step 2: LLM classification
      llm_result = @llm_classifier.classify(
        sender_email: email_data[:sender_email],
        sender_name: email_data[:sender_name],
        subject: email_data[:subject],
        body_text: email_data[:body_text],
        thread_context: thread_context,
        user: @user,
        gmail_thread_id: email_data[:gmail_thread_id]
      )

      # Step 3: Safety net - automated emails can't be needs_response
      if rule_result[:is_automated] && llm_result[:category] == "needs_response"
        llm_result[:category] = "fyi"
        llm_result[:reasoning] = "Overridden: automated sender detected but LLM classified as needs_response. #{llm_result[:reasoning]}"
      end

      # Step 4: Style & language resolution
      resolved_style = resolve_style(email_data[:sender_email], llm_result[:communication_style])
      resolved_language = resolve_language(email_data[:sender_email], llm_result[:detected_language])

      # Step 5: Store results
      email = find_or_create_email(email_data, llm_result, resolved_style, resolved_language)

      # Step 6: Apply Gmail label
      apply_labels(email)

      # Step 7: Log event
      email.log_event(
        "classified",
        "Classified as #{email.classification} (confidence: #{email.confidence})"
      )

      email
    end

    # Reclassify an existing email (manual trigger from debug UI)
    def reclassify(email)
      classify(
        email_data: {
          gmail_thread_id: email.gmail_thread_id,
          gmail_message_id: email.gmail_message_id,
          sender_email: email.sender_email,
          sender_name: email.sender_name,
          subject: email.subject,
          body_text: nil # Would need to refetch from Gmail
        },
        force: true
      )
    end

    private

    def classify_as_automated(email_data, rule_result)
      email = find_or_create_email(
        email_data,
        {
          category: "fyi",
          confidence: "high",
          reasoning: "Rule engine: #{rule_result[:reasoning]}",
          vendor_name: nil,
          communication_style: "business",
          detected_language: "cs"
        },
        "business",
        @user.setting_for("default_language") || "cs"
      )

      apply_labels(email)
      email.log_event("classified", "Auto-classified as fyi (rule: #{rule_result[:rule_name]})")
      email
    end

    def find_or_create_email(email_data, result, resolved_style, resolved_language)
      email = Email.find_or_initialize_by(
        user: @user,
        gmail_thread_id: email_data[:gmail_thread_id]
      )

      email.assign_attributes(
        gmail_message_id: email_data[:gmail_message_id],
        sender_email: email_data[:sender_email],
        sender_name: email_data[:sender_name],
        subject: email_data[:subject],
        snippet: email_data[:snippet],
        received_at: email_data[:received_at] || Time.current,
        classification: result[:category],
        confidence: result[:confidence],
        reasoning: result[:reasoning],
        detected_language: resolved_language,
        resolved_style: resolved_style,
        vendor_name: result[:vendor_name],
        processed_at: Time.current
      )

      email.save!
      email
    end

    def apply_labels(email)
      @label_manager.apply_classification_label(
        message_id: email.gmail_message_id,
        classification: email.classification
      )
    rescue Gmail::Client::GmailApiError => e
      Rails.logger.error("Failed to apply label: #{e.message}")
    end

    def resolve_style(sender_email, llm_style)
      contacts = @user.setting_for("contacts")
      return llm_style unless contacts.is_a?(Hash)

      # 1. Exact email match
      style_overrides = contacts["style_overrides"]
      if style_overrides.is_a?(Hash)
        exact = style_overrides[sender_email]
        return exact if exact.present?
      end

      # 2. Domain pattern match
      domain_overrides = contacts["domain_overrides"]
      if domain_overrides.is_a?(Hash)
        domain = sender_email.split("@").last
        domain_style = domain_overrides[domain]
        return domain_style if domain_style.present?
      end

      # 3. LLM-determined style
      llm_style || "business"
    end

    def resolve_language(sender_email, llm_language)
      contacts = @user.setting_for("contacts")
      if contacts.is_a?(Hash)
        language_overrides = contacts["language_overrides"]
        if language_overrides.is_a?(Hash)
          exact = language_overrides[sender_email]
          return exact if exact.present?

          domain = sender_email.split("@").last
          domain_lang = language_overrides[domain]
          return domain_lang if domain_lang.present?
        end
      end

      llm_language || @user.setting_for("default_language") || "cs"
    end
  end
end
