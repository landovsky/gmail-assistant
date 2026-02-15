# frozen_string_literal: true

require "rails_helper"

RSpec.describe LlmGateway do
  let(:gateway) { described_class.new(base_url: "http://localhost:4000") }
  let(:user) { create(:user) }

  describe "#chat" do
    let(:messages) do
      [
        { role: "system", content: "You are a classifier." },
        { role: "user", content: "Classify this email." }
      ]
    end

    let(:success_response) do
      {
        "choices" => [
          {
            "message" => { "content" => '{"category": "needs_response"}' },
            "finish_reason" => "stop"
          }
        ],
        "usage" => {
          "prompt_tokens" => 100,
          "completion_tokens" => 50,
          "total_tokens" => 150
        }
      }
    end

    before do
      stub_request(:post, "http://localhost:4000/v1/chat/completions")
        .to_return(
          status: 200,
          body: success_response.to_json,
          headers: { "Content-Type" => "application/json" }
        )
    end

    it "makes a successful API call and returns parsed response" do
      result = gateway.chat(
        model: "gemini/gemini-2.0-flash",
        messages: messages,
        user: user,
        call_type: "classify"
      )

      expect(result[:response_text]).to eq('{"category": "needs_response"}')
      expect(result[:prompt_tokens]).to eq(100)
      expect(result[:completion_tokens]).to eq(50)
    end

    it "logs the call to LlmCall table" do
      expect do
        gateway.chat(
          model: "gemini/gemini-2.0-flash",
          messages: messages,
          user: user,
          call_type: "classify"
        )
      end.to change(LlmCall, :count).by(1)

      call = LlmCall.last
      expect(call.call_type).to eq("classify")
      expect(call.model).to eq("gemini/gemini-2.0-flash")
      expect(call.system_prompt).to eq("You are a classifier.")
      expect(call.user_message).to eq("Classify this email.")
      expect(call.prompt_tokens).to eq(100)
    end

    context "when rate limited" do
      before do
        stub_request(:post, "http://localhost:4000/v1/chat/completions")
          .to_return(status: 429, body: "Rate limit exceeded")
      end

      it "raises RateLimitError and logs the failure" do
        expect do
          gateway.chat(model: "test", messages: messages, user: user, call_type: "classify")
        end.to raise_error(LlmGateway::RateLimitError)

        call = LlmCall.last
        expect(call.error).to include("Rate limit")
      end
    end

    context "when server error" do
      before do
        stub_request(:post, "http://localhost:4000/v1/chat/completions")
          .to_return(status: 500, body: "Internal Server Error")
      end

      it "raises LlmError" do
        expect do
          gateway.chat(model: "test", messages: messages, user: user, call_type: "classify")
        end.to raise_error(LlmGateway::LlmError)
      end
    end

    context "when connection refused" do
      before do
        stub_request(:post, "http://localhost:4000/v1/chat/completions")
          .to_raise(Errno::ECONNREFUSED)
      end

      it "raises LlmError" do
        expect do
          gateway.chat(model: "test", messages: messages, user: user, call_type: "classify")
        end.to raise_error(LlmGateway::LlmError, /connection refused/i)
      end
    end
  end

  describe "#chat_json" do
    let(:messages) { [{ role: "user", content: "test" }] }

    before do
      stub_request(:post, "http://localhost:4000/v1/chat/completions")
        .to_return(
          status: 200,
          body: {
            "choices" => [{ "message" => { "content" => '{"key": "value"}' }, "finish_reason" => "stop" }],
            "usage" => { "prompt_tokens" => 10, "completion_tokens" => 5, "total_tokens" => 15 }
          }.to_json,
          headers: { "Content-Type" => "application/json" }
        )
    end

    it "returns parsed JSON response" do
      result = gateway.chat_json(
        model: "test",
        messages: messages,
        user: user,
        call_type: "classify"
      )

      expect(result[:parsed_response]).to eq({ "key" => "value" })
    end
  end
end
