# frozen_string_literal: true

module Agent
  # Central registry for all tools available to agents.
  # Tools are registered with name, description, parameter schema, and handler.
  class ToolRegistry
    class ToolNotFoundError < StandardError; end

    ToolDefinition = Struct.new(:name, :description, :parameters, :handler, keyword_init: true)

    class << self
      def instance
        @instance ||= new
      end

      delegate :register, :get, :tools_for_profile, :all_schemas, :execute, to: :instance
    end

    def initialize
      @tools = {}
      register_builtin_tools
    end

    def register(name:, description:, parameters:, handler:)
      @tools[name.to_s] = ToolDefinition.new(
        name: name.to_s,
        description: description,
        parameters: parameters,
        handler: handler
      )
    end

    def get(name)
      @tools[name.to_s] || raise(ToolNotFoundError, "Tool '#{name}' not found")
    end

    # Return OpenAI-compatible tool schemas for a list of tool names.
    def tools_for_profile(tool_names)
      tool_names.map do |name|
        tool = get(name)
        {
          type: "function",
          function: {
            name: tool.name,
            description: tool.description,
            parameters: tool.parameters
          }
        }
      end
    end

    def all_schemas
      @tools.values.map do |tool|
        {
          type: "function",
          function: {
            name: tool.name,
            description: tool.description,
            parameters: tool.parameters
          }
        }
      end
    end

    # Execute a tool by name with given arguments and context.
    def execute(name, arguments:, context: {})
      tool = get(name)
      tool.handler.call(arguments: arguments, context: context)
    rescue StandardError => e
      "Error executing tool '#{name}': #{e.message}"
    end

    private

    def register_builtin_tools
      register_send_reply
      register_create_draft
      register_escalate
      register_search_drugs
      register_manage_reservation
      register_web_search
    end

    def register_send_reply
      register(
        name: "send_reply",
        description: "Send a reply email immediately without human review. Use only for straightforward queries with high confidence.",
        parameters: {
          type: "object",
          properties: {
            message: { type: "string", description: "The reply message text" },
            thread_id: { type: "string", description: "Gmail thread ID to reply to" }
          },
          required: %w[message thread_id]
        },
        handler: Agent::Tools::SendReply
      )
    end

    def register_create_draft
      register(
        name: "create_draft",
        description: "Create an email draft for human review before sending. Use for complex queries, reservations, or uncertain responses.",
        parameters: {
          type: "object",
          properties: {
            message: { type: "string", description: "The draft message text" },
            thread_id: { type: "string", description: "Gmail thread ID to reply to" }
          },
          required: %w[message thread_id]
        },
        handler: Agent::Tools::CreateDraft
      )
    end

    def register_escalate
      register(
        name: "escalate",
        description: "Flag a message for human attention. Use for medical advice, disputes, or issues beyond agent capabilities.",
        parameters: {
          type: "object",
          properties: {
            reason: { type: "string", description: "Reason for escalation" },
            thread_id: { type: "string", description: "Gmail thread ID to escalate" }
          },
          required: %w[reason thread_id]
        },
        handler: Agent::Tools::Escalate
      )
    end

    def register_search_drugs
      register(
        name: "search_drugs",
        description: "Search drug availability in pharmacy database.",
        parameters: {
          type: "object",
          properties: {
            drug_name: { type: "string", description: "Name of the drug to search for" }
          },
          required: %w[drug_name]
        },
        handler: Agent::Tools::SearchDrugs
      )
    end

    def register_manage_reservation
      register(
        name: "manage_reservation",
        description: "Create, check, or cancel a pharmacy drug reservation.",
        parameters: {
          type: "object",
          properties: {
            action: { type: "string", enum: %w[create check cancel], description: "Action to perform" },
            drug_name: { type: "string", description: "Drug name" },
            patient_name: { type: "string", description: "Patient name" },
            patient_email: { type: "string", description: "Patient email" }
          },
          required: %w[action drug_name patient_name]
        },
        handler: Agent::Tools::ManageReservation
      )
    end

    def register_web_search
      register(
        name: "web_search",
        description: "Search the web for drug information, side effects, or interactions.",
        parameters: {
          type: "object",
          properties: {
            query: { type: "string", description: "Search query" }
          },
          required: %w[query]
        },
        handler: Agent::Tools::WebSearch
      )
    end
  end
end
