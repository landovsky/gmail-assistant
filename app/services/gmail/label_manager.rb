# frozen_string_literal: true

module Gmail
  # Manages Gmail labels for a user: creates GMA-prefixed labels,
  # maps them to the UserLabel table, and applies/removes labels on messages.
  class LabelManager
    LABEL_PREFIX = "GMA"

    # Standard label definitions: key => display name suffix
    STANDARD_LABELS = {
      "needs_response" => "Needs Response",
      "action_required" => "Action Required",
      "payment_request" => "Payment Request",
      "fyi" => "FYI",
      "waiting" => "Waiting",
      "outbox" => "Outbox",
      "rework" => "Rework",
      "done" => "Done"
    }.freeze

    def initialize(user:, gmail_client: nil)
      @user = user
      @gmail_client = gmail_client || Gmail::Client.new(user: user)
    end

    # Creates all standard labels in Gmail and maps them in the database.
    # Idempotent: skips labels that already exist.
    def ensure_labels!
      existing_labels = @gmail_client.list_labels
      existing_by_name = existing_labels.each_with_object({}) { |l, h| h[l.name] = l }

      STANDARD_LABELS.each do |key, name_suffix|
        full_name = "#{LABEL_PREFIX}/#{name_suffix}"

        gmail_label = if existing_by_name[full_name]
                        existing_by_name[full_name]
                      else
                        @gmail_client.create_label(full_name)
                      end

        UserLabel.find_or_create_by!(user: @user, label_key: key) do |label|
          label.gmail_label_id = gmail_label.id
          label.gmail_label_name = full_name
        end
      end
    end

    # Apply a classification label to a Gmail message.
    # Also removes any other classification labels.
    def apply_classification_label(message_id:, classification:)
      target_label = @user.label_for(classification)
      return unless target_label

      # Remove other classification labels
      other_labels = @user.user_labels.classification_labels.where.not(label_key: classification)
      remove_ids = other_labels.pluck(:gmail_label_id)

      @gmail_client.modify_message_labels(
        message_id,
        add_label_ids: [target_label.gmail_label_id],
        remove_label_ids: remove_ids
      )
    end

    # Apply a workflow label (outbox, rework, done)
    def apply_workflow_label(message_id:, label_key:)
      label = @user.label_for(label_key)
      return unless label

      @gmail_client.modify_message_labels(
        message_id,
        add_label_ids: [label.gmail_label_id]
      )
    end

    # Remove a specific label from a message
    def remove_label(message_id:, label_key:)
      label = @user.label_for(label_key)
      return unless label

      @gmail_client.modify_message_labels(
        message_id,
        remove_label_ids: [label.gmail_label_id]
      )
    end

    # Get the Gmail label ID for a given logical key
    def label_id_for(key)
      @user.label_for(key)&.gmail_label_id
    end

    # Check which GMA labels are on a message
    def gma_labels_on_message(message_label_ids)
      return [] unless message_label_ids

      gma_label_ids = @user.user_labels.pluck(:gmail_label_id)
      message_label_ids.select { |id| gma_label_ids.include?(id) }
    end
  end
end
