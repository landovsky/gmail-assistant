# frozen_string_literal: true

module Agent
  module Tools
    # Search the web for drug information, side effects, or interactions.
    # Currently returns mock data -- ready for real implementation.
    module WebSearch
      module_function

      def call(arguments:, context: {})
        query = arguments["query"]

        # Real implementation would use a search API (Google, Bing, etc.)
        <<~RESULT
          Web search results for "#{query}":
          1. Drug information portal - General overview and dosage guidelines
          2. Interactions database - No major interactions found
          3. Patient leaflet - Standard usage instructions and side effects
          Note: This is mock data. Connect to a search API for real results.
        RESULT
      end
    end
  end
end
