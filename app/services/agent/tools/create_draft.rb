# frozen_string_literal: true

module Agent
  module Tools
    # Create an email draft for human review before sending.
    module CreateDraft
      module_function

      def call(arguments:, context: {})
        message = arguments["message"]
        thread_id = arguments["thread_id"]
        user = context[:user]

        return "Error: missing user context" unless user

        gmail_client = context[:gmail_client] || Gmail::Client.new(user: user)

        # Get the thread to determine reply-to address
        thread = gmail_client.get_thread(thread_id)
        return "Error: thread not found" unless thread&.messages&.any?

        last_message = thread.messages.last
        headers = last_message.payload&.headers || []
        reply_to = headers.find { |h| h.name == "Reply-To" }&.value
        from = headers.find { |h| h.name == "From" }&.value
        subject = headers.find { |h| h.name == "Subject" }&.value
        to_address = reply_to || from

        draft = gmail_client.create_draft(
          to: to_address,
          subject: "Re: #{subject}",
          body: message,
          thread_id: thread_id,
          in_reply_to: last_message.id
        )

        # Update email record
        email = user.emails.find_by(gmail_thread_id: thread_id)
        if email
          email.mark_drafted!(draft_id: draft.id)
          email.log_event("draft_created", "Agent created draft for review", draft_id: draft.id)
        end

        # Apply outbox label
        label_manager = Gmail::LabelManager.new(user: user, gmail_client: gmail_client)
        label_manager.apply_workflow_label(message_id: last_message.id, label_key: "outbox")

        "Draft created successfully (ID: #{draft.id}) for #{to_address}"
      rescue StandardError => e
        "Error creating draft: #{e.message}"
      end
    end
  end
end
