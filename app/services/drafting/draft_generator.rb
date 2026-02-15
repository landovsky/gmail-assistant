# frozen_string_literal: true

module Drafting
  # Generates email draft responses using LLM and creates them in Gmail.
  # Handles both initial drafts and rework iterations.
  class DraftGenerator
    SCISSORS_MARKER = "\n---\n✂️\n"

    DRAFT_SYSTEM_PROMPT = <<~PROMPT
      You are an email assistant writing a draft reply on behalf of the user.

      Guidelines:
      - Match the sender's communication style and language
      - Be helpful, concise, and professional
      - Directly address the sender's questions or requests
      - Use appropriate greeting and sign-off for the style
      - Do NOT include the scissors marker (✂️) in your response
      - Do NOT include any meta-instructions or notes to the user
      - Write ONLY the email body content

      Style guidelines:
      %<style_guide>s

      Language: %<language>s
      Sign-off name: %<sign_off>s
    PROMPT

    def initialize(user:, gmail_client: nil, llm_gateway: nil)
      @user = user
      @gmail_client = gmail_client || Gmail::Client.new(user: user)
      @llm = llm_gateway || LlmGateway.new
      @context_gatherer = ContextGatherer.new(
        user: user, gmail_client: @gmail_client, llm_gateway: @llm
      )
      @label_manager = Gmail::LabelManager.new(user: user, gmail_client: @gmail_client)
    end

    # Generate an initial draft for an email.
    # Returns the updated Email record.
    def generate(email, user_instructions: nil)
      # Step 1: Trash any stale drafts
      trash_existing_draft(email)

      # Step 2: Gather related context
      context = @context_gatherer.gather(
        sender_email: email.sender_email,
        subject: email.subject,
        body_text: nil, # Would refetch from Gmail if needed
        gmail_thread_id: email.gmail_thread_id
      )

      # Step 3: Generate draft via LLM
      draft_text = call_llm_for_draft(email, context: context, user_instructions: user_instructions)

      # Step 4: Create Gmail draft with scissors marker
      draft_html = format_draft_html(draft_text)
      gmail_draft = @gmail_client.create_draft(
        thread_id: email.gmail_thread_id,
        to: email.sender_email,
        subject: "Re: #{email.subject}",
        body_html: draft_html
      )

      # Step 5: Update email record
      email.mark_drafted!(draft_id: gmail_draft.id)

      # Step 6: Apply outbox label
      @label_manager.apply_workflow_label(
        message_id: email.gmail_message_id,
        label_key: "outbox"
      )

      # Step 7: Log event
      email.log_event("draft_created", "Initial draft generated", draft_id: gmail_draft.id)

      email
    rescue Gmail::Client::GmailApiError, LlmGateway::LlmError => e
      email.log_event("error", "Draft generation failed: #{e.message}")
      raise
    end

    # Rework an existing draft based on user feedback.
    # Returns the updated Email record.
    def rework(email, instruction:)
      # Step 1: Check rework limit
      unless email.request_rework!(instruction: instruction)
        # Limit reached - move to action_required
        @label_manager.remove_label(message_id: email.gmail_message_id, label_key: "outbox")
        @label_manager.apply_classification_label(
          message_id: email.gmail_message_id,
          classification: "action_required"
        )
        return email
      end

      # Step 2: Gather fresh context
      context = @context_gatherer.gather(
        sender_email: email.sender_email,
        subject: email.subject,
        body_text: nil,
        gmail_thread_id: email.gmail_thread_id
      )

      # Step 3: Generate reworked draft
      draft_text = call_llm_for_rework(email, instruction: instruction, context: context)

      # Step 4: Trash old draft and create new one
      trash_existing_draft(email)

      draft_html = format_draft_html(draft_text)
      gmail_draft = @gmail_client.create_draft(
        thread_id: email.gmail_thread_id,
        to: email.sender_email,
        subject: "Re: #{email.subject}",
        body_html: draft_html
      )

      # Step 5: Update email record
      email.update!(
        draft_id: gmail_draft.id,
        status: "drafted",
        drafted_at: Time.current
      )

      # Step 6: Log event
      email.log_event("draft_reworked",
                       "Draft reworked (iteration #{email.rework_count})",
                       draft_id: gmail_draft.id)

      email
    rescue Gmail::Client::GmailApiError, LlmGateway::LlmError => e
      email.log_event("error", "Draft rework failed: #{e.message}")
      raise
    end

    private

    def call_llm_for_draft(email, context: nil, user_instructions: nil)
      system_prompt = build_system_prompt(email)

      user_message = build_draft_user_message(email, context: context, user_instructions: user_instructions)

      result = @llm.chat(
        model: AppConfig.llm.draft_model,
        messages: [
          { role: "system", content: system_prompt },
          { role: "user", content: user_message }
        ],
        max_tokens: AppConfig.llm.max_draft_tokens,
        temperature: 0.3,
        user: @user,
        gmail_thread_id: email.gmail_thread_id,
        call_type: "draft"
      )

      result[:response_text]
    end

    def call_llm_for_rework(email, instruction:, context: nil)
      system_prompt = build_system_prompt(email)

      user_message = build_rework_user_message(email, instruction: instruction, context: context)

      result = @llm.chat(
        model: AppConfig.llm.draft_model,
        messages: [
          { role: "system", content: system_prompt },
          { role: "user", content: user_message }
        ],
        max_tokens: AppConfig.llm.max_draft_tokens,
        temperature: 0.3,
        user: @user,
        gmail_thread_id: email.gmail_thread_id,
        call_type: "rework"
      )

      result[:response_text]
    end

    def build_system_prompt(email)
      sign_off = @user.setting_for("sign_off_name") || @user.display_name || "User"
      style_guide = style_guidelines(email.resolved_style)

      format(DRAFT_SYSTEM_PROMPT,
             style_guide: style_guide,
             language: email.detected_language,
             sign_off: sign_off)
    end

    def build_draft_user_message(email, context: nil, user_instructions: nil)
      parts = []
      parts << "Write a reply to this email:"
      parts << ""
      parts << "From: #{email.sender_name} <#{email.sender_email}>"
      parts << "Subject: #{email.subject}"
      parts << "Body: #{email.snippet}"
      parts << ""

      if context
        parts << context
        parts << ""
      end

      if user_instructions
        parts << "User instructions: #{user_instructions}"
        parts << ""
      end

      parts.join("\n")
    end

    def build_rework_user_message(email, instruction:, context: nil)
      parts = []
      parts << "Rework this draft reply based on the user's feedback."
      parts << ""
      parts << "Original email from: #{email.sender_name} <#{email.sender_email}>"
      parts << "Subject: #{email.subject}"
      parts << ""
      parts << "User feedback: #{instruction}"
      parts << ""

      if context
        parts << context
        parts << ""
      end

      parts.join("\n")
    end

    def format_draft_html(draft_text)
      # Convert text to simple HTML with scissors marker
      html_body = draft_text.gsub("\n", "<br>")
      "#{html_body}<br>#{SCISSORS_MARKER.gsub("\n", '<br>')}"
    end

    def trash_existing_draft(email)
      return unless email.draft_id.present?

      @gmail_client.delete_draft(email.draft_id)
      email.log_event("draft_trashed", "Old draft trashed", draft_id: email.draft_id)
    rescue Gmail::Client::NotFoundError
      # Draft already deleted (user may have sent it)
      Rails.logger.debug("Draft #{email.draft_id} already deleted")
    end

    def style_guidelines(style)
      case style
      when "formal"
        "Use very polite, structured language. Traditional business formalities. Complete sentences, proper grammar. Respectful distance."
      when "informal"
        "Use casual, friendly tone. Relaxed grammar. Conversational style. Personal connection."
      else # business (default)
        "Professional but approachable. Clear and concise. Balance formality with friendliness. Modern business communication."
      end
    end
  end
end
