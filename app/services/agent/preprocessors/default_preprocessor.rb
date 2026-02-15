# frozen_string_literal: true

module Agent
  module Preprocessors
    # Simple pass-through preprocessor for standard emails.
    class DefaultPreprocessor
      def process(subject:, body:, headers: {})
        {
          subject: subject,
          body: body,
          patient_name: nil,
          patient_email: nil,
          formatted_message: "Subject: #{subject}\n\nMessage:\n#{body}"
        }
      end
    end
  end
end
