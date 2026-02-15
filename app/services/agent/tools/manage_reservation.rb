# frozen_string_literal: true

module Agent
  module Tools
    # Create, check, or cancel pharmacy drug reservations.
    # Currently returns mock data -- ready for real implementation.
    module ManageReservation
      module_function

      def call(arguments:, context: {})
        action = arguments["action"]
        drug_name = arguments["drug_name"]
        patient_name = arguments["patient_name"]
        patient_email = arguments["patient_email"]

        case action
        when "create"
          reservation_id = "RES-#{SecureRandom.hex(4).upcase}"
          "Reservation created: #{reservation_id} for #{drug_name} (patient: #{patient_name}). " \
            "Valid for 48 hours. Note: This is mock data."
        when "check"
          "Reservation status for #{drug_name} (patient: #{patient_name}): Active, pickup by tomorrow 18:00. " \
            "Note: This is mock data."
        when "cancel"
          "Reservation for #{drug_name} (patient: #{patient_name}) has been cancelled. " \
            "Note: This is mock data."
        else
          "Unknown action: #{action}. Valid actions: create, check, cancel."
        end
      end
    end
  end
end
