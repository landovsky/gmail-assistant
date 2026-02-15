# frozen_string_literal: true

require "rails_helper"

RSpec.describe Agent::ToolRegistry do
  let(:registry) { described_class.new }

  describe "#register and #get" do
    it "registers and retrieves a tool" do
      registry.register(
        name: "test_tool",
        description: "A test tool",
        parameters: { type: "object", properties: {} },
        handler: ->(arguments:, context:) { "test result" }
      )

      tool = registry.get("test_tool")
      expect(tool.name).to eq("test_tool")
      expect(tool.description).to eq("A test tool")
    end

    it "raises ToolNotFoundError for unknown tools" do
      expect {
        registry.get("nonexistent")
      }.to raise_error(Agent::ToolRegistry::ToolNotFoundError)
    end
  end

  describe "builtin tools" do
    it "registers send_reply tool" do
      tool = registry.get("send_reply")
      expect(tool.name).to eq("send_reply")
      expect(tool.description).to include("reply")
    end

    it "registers create_draft tool" do
      tool = registry.get("create_draft")
      expect(tool.name).to eq("create_draft")
      expect(tool.description).to include("draft")
    end

    it "registers escalate tool" do
      tool = registry.get("escalate")
      expect(tool.name).to eq("escalate")
      expect(tool.description).to include("human")
    end

    it "registers search_drugs tool" do
      tool = registry.get("search_drugs")
      expect(tool.name).to eq("search_drugs")
    end

    it "registers manage_reservation tool" do
      tool = registry.get("manage_reservation")
      expect(tool.name).to eq("manage_reservation")
    end

    it "registers web_search tool" do
      tool = registry.get("web_search")
      expect(tool.name).to eq("web_search")
    end
  end

  describe "#tools_for_profile" do
    it "returns OpenAI-compatible tool schemas" do
      schemas = registry.tools_for_profile(%w[search_drugs escalate])

      expect(schemas.size).to eq(2)
      expect(schemas.first[:type]).to eq("function")
      expect(schemas.first[:function][:name]).to eq("search_drugs")
      expect(schemas.first[:function][:parameters]).to be_a(Hash)
    end
  end

  describe "#execute" do
    it "executes search_drugs tool" do
      result = registry.execute("search_drugs", arguments: { "drug_name" => "Ibuprofen" }, context: {})
      expect(result).to include("Ibuprofen")
      expect(result).to include("search results")
    end

    it "executes manage_reservation tool" do
      result = registry.execute(
        "manage_reservation",
        arguments: { "action" => "create", "drug_name" => "Aspirin", "patient_name" => "Jan" },
        context: {}
      )
      expect(result).to include("Reservation created")
      expect(result).to include("RES-")
    end

    it "executes web_search tool" do
      result = registry.execute("web_search", arguments: { "query" => "aspirin dosage" }, context: {})
      expect(result).to include("aspirin dosage")
    end

    it "returns error string for unknown tool" do
      result = registry.execute("nonexistent", arguments: {}, context: {})
      expect(result).to include("Error")
    end
  end
end
