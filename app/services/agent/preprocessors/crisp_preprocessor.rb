# frozen_string_literal: true

module Agent
  module Preprocessors
    # Extracts structured data from emails forwarded through Crisp helpdesk.
    class CrispPreprocessor
      NAME_PATTERNS = [
        /(From|Od|Name|Jmeno):\s*(.+)/i
      ].freeze

      SEPARATOR_PATTERN = /-{3,}|={3,}|_{3,}/

      EMAIL_PATTERN = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b/i

      def process(subject:, body:, headers: {})
        patient_name = extract_patient_name(body)
        patient_email = extract_patient_email(body, headers)
        original_message = extract_original_message(body)

        formatted = build_formatted_message(
          subject: subject,
          patient_name: patient_name,
          patient_email: patient_email,
          message: original_message
        )

        {
          subject: subject,
          body: original_message,
          patient_name: patient_name,
          patient_email: patient_email,
          formatted_message: formatted
        }
      end

      private

      def extract_patient_name(body)
        NAME_PATTERNS.each do |pattern|
          match = body.match(pattern)
          return match[2].strip if match
        end
        nil
      end

      def extract_patient_email(body, headers)
        # Check Reply-To header first
        reply_to = headers["Reply-To"]
        if reply_to
          match = reply_to.match(EMAIL_PATTERN)
          return match[0] if match
        end

        # Check X-Forwarded-From
        forwarded = headers["X-Forwarded-From"]
        if forwarded
          match = forwarded.match(EMAIL_PATTERN)
          return match[0] if match
        end

        # Extract from body
        match = body.match(EMAIL_PATTERN)
        match ? match[0] : nil
      end

      def extract_original_message(body)
        # Split at separator and take the content after it (the forwarded message)
        parts = body.split(SEPARATOR_PATTERN, 2)
        if parts.length > 1
          parts[1].strip
        else
          # No separator found; try to strip common forwarding headers
          body.gsub(/^(From|Od|Name|Jmeno|Email|Reply-To):.*\n/i, "").strip
        end
      end

      def build_formatted_message(subject:, patient_name:, patient_email:, message:)
        lines = ["Subject: #{subject}"]
        lines << "Patient name: #{patient_name}" if patient_name
        lines << "Patient email: #{patient_email}" if patient_email
        lines << ""
        lines << "Message:"
        lines << message
        lines.join("\n")
      end
    end
  end
end
