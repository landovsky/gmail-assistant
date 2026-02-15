# frozen_string_literal: true

module Agent
  module Tools
    # Search drug availability in pharmacy database.
    # Currently returns mock data -- ready for real implementation.
    module SearchDrugs
      module_function

      def call(arguments:, context: {})
        drug_name = arguments["drug_name"]

        # Real implementation would query pharmacy database/API
        # For now, return structured mock data
        <<~RESULT
          Drug search results for "#{drug_name}":
          - Availability: In stock at 3 nearby pharmacies
          - Price range: 89-129 CZK
          - Requires prescription: No
          - Alternative brands available: Yes
          Note: This is mock data. Connect to pharmacy database for real results.
        RESULT
      end
    end
  end
end
