# frozen_string_literal: true

require "rails_helper"

RSpec.describe Agent::Loop do
  let(:user) { create(:user) }
  let(:gmail_client) { instance_double(Gmail::Client) }
  let(:llm) { instance_double(LlmGateway) }
  let(:loop_instance) { described_class.new(user: user, gmail_client: gmail_client) }

  before do
    allow(LlmGateway).to receive(:new).and_return(llm)
    # Create user labels for tools that need them
    %w[needs_response action_required payment_request fyi waiting outbox rework done].each_with_index do |key, i|
      create(:user_label, user: user, label_key: key, gmail_label_id: "Label_#{i}")
    end
  end

  describe "#execute" do
    let(:thread_id) { "thread_123" }

    context "when LLM returns final answer without tool use" do
      it "completes the agent run" do
        allow(llm).to receive(:chat).and_return({
          content: "Task completed. Email has been processed.",
          response_text: "Task completed. Email has been processed.",
          tool_calls: nil,
          prompt_tokens: 100,
          completion_tokens: 50,
          total_tokens: 150,
          finish_reason: "stop"
        })

        agent_run = loop_instance.execute(
          gmail_thread_id: thread_id,
          profile_name: "default",
          user_message: "Process this email"
        )

        expect(agent_run.status).to eq("completed")
        expect(agent_run.final_message).to include("Task completed")
        expect(agent_run.iterations).to eq(0) # No tool calls
      end
    end

    context "when LLM uses a tool then provides final answer" do
      it "executes tool and completes" do
        # First call: LLM requests tool use
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
            content: "Found information about Ibuprofen. Task complete.",
            response_text: "Found information about Ibuprofen. Task complete.",
            tool_calls: nil,
            prompt_tokens: 200,
            completion_tokens: 60,
            total_tokens: 260,
            finish_reason: "stop"
          }
        )

        agent_run = loop_instance.execute(
          gmail_thread_id: thread_id,
          profile_name: "pharmacy",
          user_message: "Check Ibuprofen availability"
        )

        expect(agent_run.status).to eq("completed")
        expect(agent_run.iterations).to eq(1) # One tool call
        tool_calls = agent_run.parsed_tool_calls
        expect(tool_calls.size).to eq(1)
        expect(tool_calls.first["tool"]).to eq("search_drugs")
      end
    end

    context "when max iterations is reached" do
      it "stops with max_iterations status" do
        # Always return tool calls to force iteration
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

        # Use a profile with max_iterations: 2
        allow(AppConfig).to receive(:get).with(:agent, :profiles).and_return({
          "test_loop" => { "max_iterations" => 2, "tools" => %w[search_drugs] }
        })

        agent_run = loop_instance.execute(
          gmail_thread_id: thread_id,
          profile_name: "test_loop",
          user_message: "Process this"
        )

        expect(agent_run.status).to eq("max_iterations")
        expect(agent_run.iterations).to eq(2)
      end
    end

    context "when an error occurs" do
      it "marks the run as error" do
        allow(llm).to receive(:chat).and_raise(LlmGateway::LlmError, "API connection failed")

        agent_run = loop_instance.execute(
          gmail_thread_id: thread_id,
          profile_name: "default",
          user_message: "Process this"
        )

        expect(agent_run.status).to eq("error")
        expect(agent_run.error).to include("API connection failed")
      end
    end

    context "when email record exists" do
      it "logs events on the email" do
        email = create(:email, user: user, gmail_thread_id: thread_id)

        allow(llm).to receive(:chat).and_return({
          content: "Done",
          response_text: "Done",
          tool_calls: nil,
          prompt_tokens: 50,
          completion_tokens: 10,
          total_tokens: 60,
          finish_reason: "stop"
        })

        loop_instance.execute(
          gmail_thread_id: thread_id,
          profile_name: "default",
          user_message: "Process this"
        )

        events = EmailEvent.where(gmail_thread_id: thread_id)
        expect(events.map(&:event_type)).to include("agent_completed")
      end
    end
  end
end
