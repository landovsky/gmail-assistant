# frozen_string_literal: true

require "rails_helper"

RSpec.describe Classification::Pipeline do
  let(:user) { create(:user) }
  let(:gmail_client) { instance_double(Gmail::Client) }
  let(:llm_gateway) { instance_double(LlmGateway) }
  let(:pipeline) { described_class.new(user: user, gmail_client: gmail_client, llm_gateway: llm_gateway) }

  # Create user labels so label_manager can work
  before do
    %w[needs_response action_required payment_request fyi waiting outbox rework done].each_with_index do |key, i|
      create(:user_label, user: user, label_key: key, gmail_label_id: "Label_#{i}")
    end
    allow(gmail_client).to receive(:modify_message_labels)
  end

  let(:email_data) do
    {
      gmail_thread_id: "thread_1",
      gmail_message_id: "msg_1",
      sender_email: "client@example.com",
      sender_name: "Client Name",
      subject: "Quick question",
      snippet: "Can you send the report?",
      body_text: "Hi, can you send me the report by Friday?",
      received_at: 1.hour.ago
    }
  end

  describe "#classify" do
    context "when email is from an automated sender" do
      let(:automated_email_data) do
        email_data.merge(sender_email: "noreply@company.com", gmail_thread_id: "thread_auto")
      end

      it "classifies as fyi without calling LLM" do
        expect(llm_gateway).not_to receive(:chat_json)

        email = pipeline.classify(email_data: automated_email_data)
        expect(email.classification).to eq("fyi")
        expect(email.confidence).to eq("high")
        expect(email.reasoning).to include("Rule engine")
      end

      it "applies the fyi Gmail label" do
        pipeline.classify(email_data: automated_email_data)
        expect(gmail_client).to have_received(:modify_message_labels)
      end

      it "logs a classified event" do
        pipeline.classify(email_data: automated_email_data)
        event = EmailEvent.last
        expect(event.event_type).to eq("classified")
      end
    end

    context "when email needs LLM classification" do
      before do
        allow(llm_gateway).to receive(:chat_json).and_return(
          response_text: '{"category": "needs_response"}',
          parsed_response: {
            "category" => "needs_response",
            "communication_style" => "business",
            "detected_language" => "en",
            "confidence" => "high",
            "reasoning" => "Direct question requiring reply",
            "vendor_name" => nil
          },
          prompt_tokens: 100,
          completion_tokens: 50,
          total_tokens: 150,
          llm_call_id: 1
        )
      end

      it "classifies email using LLM" do
        email = pipeline.classify(email_data: email_data)

        expect(email.classification).to eq("needs_response")
        expect(email.confidence).to eq("high")
        expect(email.detected_language).to eq("en")
        expect(email.resolved_style).to eq("business")
        expect(email.reasoning).to eq("Direct question requiring reply")
      end

      it "creates the email record" do
        expect { pipeline.classify(email_data: email_data) }.to change(Email, :count).by(1)
      end

      it "applies the classification Gmail label" do
        pipeline.classify(email_data: email_data)
        expect(gmail_client).to have_received(:modify_message_labels)
      end
    end

    context "safety net: automated sender but LLM says needs_response" do
      let(:tricky_data) do
        email_data.merge(sender_email: "noreply@company.com", gmail_thread_id: "thread_trick")
      end

      it "overrides to fyi when force=true" do
        allow(llm_gateway).to receive(:chat_json).and_return(
          response_text: '{"category": "needs_response"}',
          parsed_response: {
            "category" => "needs_response",
            "communication_style" => "business",
            "detected_language" => "en",
            "confidence" => "medium",
            "reasoning" => "Seems like a question",
            "vendor_name" => nil
          },
          prompt_tokens: 50,
          completion_tokens: 30,
          total_tokens: 80,
          llm_call_id: 1
        )

        email = pipeline.classify(email_data: tricky_data, force: true)
        expect(email.classification).to eq("fyi")
        expect(email.reasoning).to include("Overridden")
      end
    end

    context "style resolution with contacts overrides" do
      before do
        user.update_setting("contacts", {
          "style_overrides" => { "vip@client.com" => "formal" },
          "domain_overrides" => { "formal-corp.com" => "formal" }
        })

        allow(llm_gateway).to receive(:chat_json).and_return(
          response_text: '{"category": "needs_response"}',
          parsed_response: {
            "category" => "needs_response",
            "communication_style" => "informal",
            "detected_language" => "en",
            "confidence" => "high",
            "reasoning" => "test",
            "vendor_name" => nil
          },
          prompt_tokens: 50,
          completion_tokens: 30,
          total_tokens: 80,
          llm_call_id: 1
        )
      end

      it "uses exact email style override" do
        data = email_data.merge(sender_email: "vip@client.com", gmail_thread_id: "thread_vip")
        email = pipeline.classify(email_data: data)
        expect(email.resolved_style).to eq("formal")
      end

      it "uses domain style override" do
        data = email_data.merge(sender_email: "person@formal-corp.com", gmail_thread_id: "thread_domain")
        email = pipeline.classify(email_data: data)
        expect(email.resolved_style).to eq("formal")
      end

      it "falls back to LLM style when no override" do
        email = pipeline.classify(email_data: email_data)
        expect(email.resolved_style).to eq("informal")
      end
    end

    context "payment request with vendor name" do
      before do
        allow(llm_gateway).to receive(:chat_json).and_return(
          response_text: '{"category": "payment_request"}',
          parsed_response: {
            "category" => "payment_request",
            "communication_style" => "formal",
            "detected_language" => "cs",
            "confidence" => "high",
            "reasoning" => "Invoice attached",
            "vendor_name" => "Acme Corp"
          },
          prompt_tokens: 50,
          completion_tokens: 30,
          total_tokens: 80,
          llm_call_id: 1
        )
      end

      it "stores vendor name" do
        email = pipeline.classify(email_data: email_data)
        expect(email.classification).to eq("payment_request")
        expect(email.vendor_name).to eq("Acme Corp")
      end
    end

    context "idempotent: re-processing same thread" do
      before do
        allow(llm_gateway).to receive(:chat_json).and_return(
          response_text: '{"category": "needs_response"}',
          parsed_response: {
            "category" => "needs_response",
            "communication_style" => "business",
            "detected_language" => "en",
            "confidence" => "high",
            "reasoning" => "test",
            "vendor_name" => nil
          },
          prompt_tokens: 50,
          completion_tokens: 30,
          total_tokens: 80,
          llm_call_id: 1
        )
      end

      it "updates existing email instead of creating duplicate" do
        pipeline.classify(email_data: email_data)
        expect { pipeline.classify(email_data: email_data) }.not_to change(Email, :count)
      end
    end
  end
end
