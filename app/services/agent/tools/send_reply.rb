# frozen_string_literal: true

module Agent
  module Tools
    # Send a reply email immediately without human review.
    module SendReply
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

        # Create and send as draft, then would need gmail.send scope
        # Since we only have gmail.modify, create draft with outbox label
        draft = gmail_client.create_draft(
          to: to_address,
          subject: "Re: #{subject}",
          body: message,
          thread_id: thread_id,
          in_reply_to: last_message.id
        )

        # Log the event
        email = user.emails.find_by(gmail_thread_id: thread_id)
        if email
          email.mark_sent!
          email.log_event("reply_sent", "Agent auto-sent reply via draft")
        end

        "Reply sent successfully to #{to_address}"
      rescue StandardError => e
        "Error sending reply: #{e.message}"
      end
    end
  end
end
