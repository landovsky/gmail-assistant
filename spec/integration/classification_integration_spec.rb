# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Classification Integration", type: :integration do
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
    # Stub as spy so we can check if called
    allow(llm).to receive(:chat_json)
    allow(llm).to receive(:chat)
  end

  describe "automation detection (rule-based)" do
    it "classifies noreply emails as fyi without LLM call" do
      pipeline = Classification::Pipeline.new(user: user, gmail_client: gmail_client, llm_gateway: llm)

      email = pipeline.classify(
        email_data: {
          gmail_thread_id: "thread_auto_1",
          gmail_message_id: "msg_auto_1",
          sender_email: "noreply@notifications.com",
          sender_name: "Notifications",
          subject: "Your order has shipped",
          snippet: "Order #12345 is on the way"
        },
        headers: {}
      )

      expect(email.classification).to eq("fyi")
      expect(email.confidence).to eq("high")
      expect(email.status).to eq("pending")

      # No LLM call should have been made
      expect(llm).not_to have_received(:chat_json)

      # Event should be logged
      events = EmailEvent.where(gmail_thread_id: "thread_auto_1")
      expect(events.map(&:event_type)).to include("classified")
    end
  end

  describe "newsletter classification" do
    it "classifies emails with List-Unsubscribe header as fyi" do
      pipeline = Classification::Pipeline.new(user: user, gmail_client: gmail_client, llm_gateway: llm)

      email = pipeline.classify(
        email_data: {
          gmail_thread_id: "thread_newsletter_1",
          gmail_message_id: "msg_newsletter_1",
          sender_email: "weekly@techdigest.com",
          sender_name: "Tech Digest",
          subject: "Weekly tech roundup"
        },
        headers: { "List-Unsubscribe" => "<mailto:unsub@techdigest.com>" }
      )

      expect(email.classification).to eq("fyi")
      expect(email.reasoning).to include("automation header")
    end
  end

  describe "direct question classification (LLM)" do
    it "classifies direct questions as needs_response via LLM" do
      allow(llm).to receive(:chat_json).and_return({
        response_text: '{"category":"needs_response","confidence":"high","reasoning":"Direct question requiring reply","communication_style":"formal","detected_language":"en","vendor_name":null}',
        parsed_response: {
          "category" => "needs_response",
          "confidence" => "high",
          "reasoning" => "Direct question requiring reply",
          "communication_style" => "formal",
          "detected_language" => "en",
          "vendor_name" => nil
        },
        prompt_tokens: 100,
        completion_tokens: 50,
        total_tokens: 150
      })

      pipeline = Classification::Pipeline.new(user: user, gmail_client: gmail_client, llm_gateway: llm)

      email = pipeline.classify(
        email_data: {
          gmail_thread_id: "thread_question_1",
          gmail_message_id: "msg_question_1",
          sender_email: "colleague@work.com",
          sender_name: "John",
          subject: "Report request",
          body_text: "Can you send me the report by Friday?"
        }
      )

      expect(email.classification).to eq("needs_response")
      expect(email.confidence).to eq("high")
      expect(email.can_draft?).to be true
    end
  end

  describe "invoice classification (LLM)" do
    it "classifies invoices as payment_request with vendor_name" do
      allow(llm).to receive(:chat_json).and_return({
        response_text: '{}',
        parsed_response: {
          "category" => "payment_request",
          "confidence" => "high",
          "reasoning" => "Invoice with amount due",
          "communication_style" => "formal",
          "detected_language" => "en",
          "vendor_name" => "Acme Corp"
        },
        prompt_tokens: 100,
        completion_tokens: 50,
        total_tokens: 150
      })

      pipeline = Classification::Pipeline.new(user: user, gmail_client: gmail_client, llm_gateway: llm)

      email = pipeline.classify(
        email_data: {
          gmail_thread_id: "thread_invoice_1",
          gmail_message_id: "msg_invoice_1",
          sender_email: "billing@acme.com",
          sender_name: "Acme Billing",
          subject: "Invoice #12345"
        }
      )

      expect(email.classification).to eq("payment_request")
      expect(email.vendor_name).to eq("Acme Corp")
      expect(email.can_draft?).to be false
    end
  end

  describe "safety net override" do
    it "overrides needs_response for automated senders" do
      pipeline = Classification::Pipeline.new(user: user, gmail_client: gmail_client, llm_gateway: llm)

      email = pipeline.classify(
        email_data: {
          gmail_thread_id: "thread_safety_1",
          gmail_message_id: "msg_safety_1",
          sender_email: "noreply@service.com",
          sender_name: "Service",
          subject: "Question about your account?"
        },
        headers: {}
      )

      expect(email.classification).to eq("fyi")
    end
  end

  describe "style resolution with overrides" do
    it "uses style override when configured" do
      create(:user_setting, user: user, key: "contacts", value: {
        "style_overrides" => { "important@client.com" => "formal" }
      }.to_json)

      allow(llm).to receive(:chat_json).and_return({
        response_text: '{}',
        parsed_response: {
          "category" => "needs_response",
          "confidence" => "high",
          "reasoning" => "Direct question",
          "communication_style" => "informal",
          "detected_language" => "en",
          "vendor_name" => nil
        },
        prompt_tokens: 50,
        completion_tokens: 30,
        total_tokens: 80
      })

      pipeline = Classification::Pipeline.new(user: user, gmail_client: gmail_client, llm_gateway: llm)

      email = pipeline.classify(
        email_data: {
          gmail_thread_id: "thread_style_1",
          gmail_message_id: "msg_style_1",
          sender_email: "important@client.com",
          sender_name: "VIP Client",
          subject: "Business inquiry"
        }
      )

      expect(email.resolved_style).to eq("formal")
    end
  end

  describe "reclassification" do
    it "reclassifies existing email with force flag" do
      email = create(:email, user: user, classification: "fyi", confidence: "high")

      allow(llm).to receive(:chat_json).and_return({
        response_text: '{}',
        parsed_response: {
          "category" => "needs_response",
          "confidence" => "high",
          "reasoning" => "Actually needs a response",
          "communication_style" => "business",
          "detected_language" => "en",
          "vendor_name" => nil
        },
        prompt_tokens: 50,
        completion_tokens: 30,
        total_tokens: 80
      })

      pipeline = Classification::Pipeline.new(user: user, gmail_client: gmail_client, llm_gateway: llm)
      reclassified = pipeline.reclassify(email)

      expect(reclassified.classification).to eq("needs_response")
      expect(reclassified.confidence).to eq("high")
    end
  end
end
