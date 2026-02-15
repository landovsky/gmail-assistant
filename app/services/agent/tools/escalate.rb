# frozen_string_literal: true

module Agent
  module Tools
    # Flag a message for human attention by applying the Action Required label.
    module Escalate
      module_function

      def call(arguments:, context: {})
        reason = arguments["reason"]
        thread_id = arguments["thread_id"]
        user = context[:user]

        return "Error: missing user context" unless user

        gmail_client = context[:gmail_client] || Gmail::Client.new(user: user)

        # Find the email
        email = user.emails.find_by(gmail_thread_id: thread_id)

        if email
          email.update!(classification: "action_required") unless email.classification == "action_required"
          email.log_event("escalated", "Agent escalated: #{reason}")
        end

        # Apply action_required label
        label_manager = Gmail::LabelManager.new(user: user, gmail_client: gmail_client)
        message_id = email&.gmail_message_id || thread_id
        label_manager.apply_workflow_label(message_id: message_id, label_key: "action_required")

        "Thread escalated for human review. Reason: #{reason}"
      rescue StandardError => e
        "Error escalating: #{e.message}"
      end
    end
  end
end
