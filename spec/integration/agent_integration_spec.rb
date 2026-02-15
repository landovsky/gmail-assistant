# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Agent System Integration", type: :integration do
  let(:user) { create(:user) }
  let(:gmail_client) { instance_double(Gmail::Client) }
  let(:llm) { instance_double(LlmGateway) }

  before do
    %w[needs_response action_required payment_request fyi waiting outbox rework done].each_with_index do |key, i|
      create(:user_label, user: user, label_key: key, gmail_label_id: "Label_#{i}")
    end

    allow(Gmail::Client).to receive(:new).and_return(gmail_client)
    allow(LlmGateway).to receive(:new).and_return(llm)
    allow(gmail_client).to receive(:modify_message_labels)
  end

  describe "routing to agent" do
    it "routes emails matching forwarded_from rule to agent" do
      rules = [
        {
          "name" => "pharmacy_support",
          "match" => { "forwarded_from" => "info@dostupnost-leku.cz" },
          "route" => "agent",
          "profile" => "pharmacy"
        },
        {
          "name" => "default",
          "match" => { "all" => true },
          "route" => "pipeline"
        }
      ]

      router = Agent::Router.new(rules: rules)
      result = router.route(sender_email: "info@dostupnost-leku.cz", subject: "Drug inquiry")

      expect(result.route).to eq("agent")
      expect(result.profile).to eq("pharmacy")
      expect(result.rule_name).to eq("pharmacy_support")
    end

    it "routes non-matching emails to pipeline" do
      rules = [
        {
          "name" => "pharmacy_support",
          "match" => { "forwarded_from" => "info@dostupnost-leku.cz" },
          "route" => "agent",
          "profile" => "pharmacy"
        },
        {
          "name" => "default",
          "match" => { "all" => true },
          "route" => "pipeline"
        }
      ]

      router = Agent::Router.new(rules: rules)
      result = router.route(sender_email: "random@person.com", subject: "Hello")

      expect(result.route).to eq("pipeline")
    end
  end

  describe "agent tool use" do
    it "executes tool calls in agent loop" do
      allow(llm).to receive(:chat).and_return(
        {
          content: nil,
          response_text: "",
          tool_calls: [
            { id: "call_1", name: "search_drugs", arguments: { "drug_name" => "Ibuprofen" } }
          ],
          prompt_tokens: 100,
          completion_tokens: 50,
          total_tokens: 150,
          finish_reason: "tool_calls"
        },
        {
          content: "Based on the search results, Ibuprofen 400mg is available.",
          response_text: "Based on the search results, Ibuprofen 400mg is available.",
          tool_calls: nil,
          prompt_tokens: 200,
          completion_tokens: 80,
          total_tokens: 280,
          finish_reason: "stop"
        }
      )

      loop_instance = Agent::Loop.new(user: user, gmail_client: gmail_client)
      agent_run = loop_instance.execute(
        gmail_thread_id: "thread_agent_1",
        profile_name: "pharmacy",
        user_message: "Patient asks about Ibuprofen availability"
      )

      expect(agent_run.status).to eq("completed")
      expect(agent_run.iterations).to eq(1)
      expect(agent_run.final_message).to include("Ibuprofen")

      tool_calls = agent_run.parsed_tool_calls
      expect(tool_calls.size).to eq(1)
      expect(tool_calls.first["tool"]).to eq("search_drugs")
      expect(tool_calls.first["input"]["drug_name"]).to eq("Ibuprofen")
    end
  end

  describe "agent auto-send via send_reply tool" do
    it "calls send_reply tool which creates a draft" do
      # The send_reply tool needs to get a thread first
      thread_messages = OpenStruct.new(
        messages: [
          OpenStruct.new(
            id: "msg_1",
            payload: OpenStruct.new(
              headers: [
                OpenStruct.new(name: "From", value: "patient@example.com"),
                OpenStruct.new(name: "Subject", value: "Drug inquiry")
              ]
            )
          )
        ]
      )
      allow(gmail_client).to receive(:get_thread).and_return(thread_messages)
      allow(gmail_client).to receive(:create_draft).and_return(OpenStruct.new(id: "draft_auto"))

      allow(llm).to receive(:chat).and_return(
        {
          content: nil,
          response_text: "",
          tool_calls: [
            {
              id: "call_send",
              name: "send_reply",
              arguments: {
                "message" => "Dear patient, Ibuprofen is available.",
                "thread_id" => "thread_agent_send"
              }
            }
          ],
          prompt_tokens: 100,
          completion_tokens: 50,
          total_tokens: 150,
          finish_reason: "tool_calls"
        },
        {
          content: "I have sent a reply to the patient.",
          response_text: "I have sent a reply to the patient.",
          tool_calls: nil,
          prompt_tokens: 200,
          completion_tokens: 40,
          total_tokens: 240,
          finish_reason: "stop"
        }
      )

      loop_instance = Agent::Loop.new(user: user, gmail_client: gmail_client)
      agent_run = loop_instance.execute(
        gmail_thread_id: "thread_agent_send",
        profile_name: "pharmacy",
        user_message: "Auto-reply to patient"
      )

      expect(agent_run.status).to eq("completed")
      tool_calls = agent_run.parsed_tool_calls
      expect(tool_calls.first["tool"]).to eq("send_reply")
    end
  end

  describe "agent escalation" do
    it "escalates when agent uses escalate tool" do
      allow(llm).to receive(:chat).and_return(
        {
          content: nil,
          response_text: "",
          tool_calls: [
            {
              id: "call_esc",
              name: "escalate",
              arguments: { "reason" => "Complex question about drug interactions", "priority" => "high" }
            }
          ],
          prompt_tokens: 100,
          completion_tokens: 30,
          total_tokens: 130,
          finish_reason: "tool_calls"
        },
        {
          content: "I have escalated this to a pharmacist for review.",
          response_text: "I have escalated this to a pharmacist for review.",
          tool_calls: nil,
          prompt_tokens: 150,
          completion_tokens: 20,
          total_tokens: 170,
          finish_reason: "stop"
        }
      )

      loop_instance = Agent::Loop.new(user: user, gmail_client: gmail_client)
      agent_run = loop_instance.execute(
        gmail_thread_id: "thread_escalate",
        profile_name: "pharmacy",
        user_message: "Complex drug interaction question"
      )

      expect(agent_run.status).to eq("completed")
      tool_calls = agent_run.parsed_tool_calls
      expect(tool_calls.first["tool"]).to eq("escalate")
      expect(tool_calls.first["input"]["reason"]).to include("drug interactions")
    end
  end

  describe "agent max iterations" do
    it "stops at max iterations and marks status" do
      allow(llm).to receive(:chat).and_return({
        content: nil,
        response_text: "",
        tool_calls: [
          { id: "call_loop", name: "search_drugs", arguments: { "drug_name" => "test" } }
        ],
        prompt_tokens: 50,
        completion_tokens: 20,
        total_tokens: 70,
        finish_reason: "tool_calls"
      })

      allow(AppConfig).to receive(:get).with(:agent, :profiles).and_return({
        "test_max" => { "max_iterations" => 3, "tools" => %w[search_drugs] }
      })

      loop_instance = Agent::Loop.new(user: user, gmail_client: gmail_client)
      agent_run = loop_instance.execute(
        gmail_thread_id: "thread_max_iter",
        profile_name: "test_max",
        user_message: "Process this"
      )

      expect(agent_run.status).to eq("max_iterations")
      expect(agent_run.iterations).to eq(3)
    end
  end

  describe "preprocessor extraction (Crisp)" do
    it "extracts patient data from forwarded Crisp email" do
      preprocessor = Agent::Preprocessors::CrispPreprocessor.new

      result = preprocessor.process(
        subject: "Patient inquiry",
        body: "From: Jan Novak\nEmail: jan@example.com\n---\nHello, I need to check if Ibuprofen 400mg is available.",
        headers: { "Reply-To" => "patient@crisp.io" }
      )

      expect(result[:patient_name]).to eq("Jan Novak")
      expect(result[:patient_email]).to eq("patient@crisp.io")
      expect(result[:body]).to include("Ibuprofen 400mg")
      expect(result[:formatted_message]).to include("Subject: Patient inquiry")
      expect(result[:formatted_message]).to include("Patient name: Jan Novak")
    end
  end
end
