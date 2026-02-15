# frozen_string_literal: true

require "rails_helper"

RSpec.describe "End-to-End Workflow", type: :request do
  include ActiveJob::TestHelper

  let(:user) { create(:user) }
  let(:gmail_client) { instance_double(Gmail::Client) }
  let(:llm) { instance_double(LlmGateway) }

  before do
    ActiveJob::Base.queue_adapter = :test

    %w[needs_response action_required payment_request fyi waiting outbox rework done].each_with_index do |key, i|
      create(:user_label, user: user, label_key: key, gmail_label_id: "Label_#{i}")
    end

    allow(Gmail::Client).to receive(:new).and_return(gmail_client)
    allow(LlmGateway).to receive(:new).and_return(llm)
    allow(gmail_client).to receive(:modify_message_labels)
    allow(gmail_client).to receive(:create_draft).and_return(OpenStruct.new(id: "draft_e2e_1"))
    allow(gmail_client).to receive(:delete_draft)
    allow(gmail_client).to receive(:list_messages).and_raise(Gmail::Client::GmailApiError, "No API")

    # Stub LLM methods as spies
    allow(llm).to receive(:chat)
    allow(llm).to receive(:chat_json)
  end

  describe "complete needs_response pipeline" do
    it "classifies, drafts, and tracks lifecycle end-to-end" do
      # Classification via LLM + context gatherer (chat_json handles both)
      allow(llm).to receive(:chat_json).and_return({
        response_text: '{}',
        parsed_response: {
          "category" => "needs_response",
          "confidence" => "high",
          "reasoning" => "Direct question requiring reply",
          "communication_style" => "business",
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
          gmail_thread_id: "thread_e2e_1",
          gmail_message_id: "msg_e2e_1",
          sender_email: "colleague@work.com",
          sender_name: "John Smith",
          subject: "Can you send me the report?",
          snippet: "Hi, can you send me the Q1 report by Friday?"
        }
      )

      expect(email.classification).to eq("needs_response")
      expect(email.status).to eq("pending")
      expect(email.can_draft?).to be true

      # Draft generation (context gathering will use chat_json which returns classification response
      # but that's ok - context gatherer handles non-array gracefully)
      allow(llm).to receive(:chat).and_return({
        content: "Hi John, Sure, I'll send the Q1 report by Friday. Best regards",
        response_text: "Hi John, Sure, I'll send the Q1 report by Friday. Best regards",
        prompt_tokens: 200,
        completion_tokens: 30,
        total_tokens: 230,
        tool_calls: nil,
        finish_reason: "stop"
      })

      generator = Drafting::DraftGenerator.new(user: user, gmail_client: gmail_client, llm_gateway: llm)
      email = generator.generate(email)

      expect(email.status).to eq("drafted")
      expect(email.draft_id).to eq("draft_e2e_1")
      expect(email.drafted_at).to be_present

      # User sends draft
      email.mark_sent!
      expect(email.status).to eq("sent")
      expect(email.acted_at).to be_present
      email.log_event("sent_detected", "Draft was sent")

      # User marks done
      email.mark_archived!
      expect(email.status).to eq("archived")
      email.log_event("archived", "User marked done")

      # Verify complete audit trail
      events = EmailEvent.where(gmail_thread_id: "thread_e2e_1").order(:created_at)
      event_types = events.pluck(:event_type)
      expect(event_types).to eq(%w[classified draft_created sent_detected archived])
    end
  end

  describe "complete fyi pipeline" do
    it "classifies as fyi, skips drafting, logs events" do
      pipeline = Classification::Pipeline.new(user: user, gmail_client: gmail_client, llm_gateway: llm)

      email = pipeline.classify(
        email_data: {
          gmail_thread_id: "thread_fyi_e2e",
          gmail_message_id: "msg_fyi_e2e",
          sender_email: "noreply@newsletter.com",
          sender_name: "Newsletter",
          subject: "Weekly digest",
          snippet: "Here are this week's top stories"
        },
        headers: { "List-Unsubscribe" => "<mailto:unsub@newsletter.com>" }
      )

      expect(email.classification).to eq("fyi")
      expect(email.status).to eq("pending")
      expect(email.can_draft?).to be false
      expect(llm).not_to have_received(:chat)

      events = EmailEvent.where(gmail_thread_id: "thread_fyi_e2e")
      expect(events.map(&:event_type)).to include("classified")
    end
  end

  describe "complete rework flow" do
    it "generates initial draft, reworks it, then user sends" do
      email = create(:email, user: user,
                     classification: "needs_response",
                     status: "pending",
                     resolved_style: "business",
                     detected_language: "en")

      # Make context gatherer's chat_json raise so it falls back gracefully
      allow(llm).to receive(:chat_json).and_raise(LlmGateway::LlmError, "No LLM for context")

      # Stub chat for draft generation
      allow(llm).to receive(:chat).and_return(
        {
          content: "Dear colleague, Thank you for your email. I will look into this matter.",
          response_text: "Dear colleague, Thank you for your email. I will look into this matter.",
          prompt_tokens: 200,
          completion_tokens: 40,
          total_tokens: 240,
          tool_calls: nil,
          finish_reason: "stop"
        },
        {
          content: "Thanks! Looking into it.",
          response_text: "Thanks! Looking into it.",
          prompt_tokens: 250,
          completion_tokens: 10,
          total_tokens: 260,
          tool_calls: nil,
          finish_reason: "stop"
        }
      )

      generator = Drafting::DraftGenerator.new(user: user, gmail_client: gmail_client, llm_gateway: llm)
      email = generator.generate(email)

      expect(email.status).to eq("drafted")
      expect(email.rework_count).to eq(0)

      # Rework
      allow(gmail_client).to receive(:create_draft).and_return(OpenStruct.new(id: "draft_rework_1"))

      email = generator.rework(email, instruction: "Make it shorter and more casual")

      expect(email.status).to eq("drafted")
      expect(email.rework_count).to eq(1)
      expect(email.draft_id).to eq("draft_rework_1")
      expect(gmail_client).to have_received(:delete_draft).with("draft_e2e_1")

      # User sends
      email.mark_sent!
      expect(email.status).to eq("sent")

      events = EmailEvent.where(gmail_thread_id: email.gmail_thread_id).order(:created_at)
      event_types = events.pluck(:event_type)
      expect(event_types).to include("draft_created", "draft_reworked")
    end
  end

  describe "classify job enqueues draft job" do
    it "enqueues DraftJob when classification is needs_response" do
      allow(llm).to receive(:chat_json).and_return({
        response_text: '{}',
        parsed_response: {
          "category" => "needs_response",
          "confidence" => "high",
          "reasoning" => "Direct question",
          "communication_style" => "business",
          "detected_language" => "en",
          "vendor_name" => nil
        },
        prompt_tokens: 100,
        completion_tokens: 50,
        total_tokens: 150
      })

      expect {
        ClassifyJob.perform_now(user.id, {
          "gmail_thread_id" => "thread_job_chain",
          "gmail_message_id" => "msg_job_chain",
          "sender_email" => "requester@work.com",
          "sender_name" => "Requester",
          "subject" => "Need help with something"
        })
      }.to have_enqueued_job(DraftJob)

      email = Email.find_by(gmail_thread_id: "thread_job_chain")
      expect(email.classification).to eq("needs_response")
      expect(email.status).to eq("pending")
    end

    it "does not enqueue DraftJob for fyi classification" do
      expect {
        ClassifyJob.perform_now(user.id, {
          "gmail_thread_id" => "thread_fyi_job",
          "gmail_message_id" => "msg_fyi_job",
          "sender_email" => "noreply@service.com",
          "sender_name" => "Service",
          "subject" => "System notification"
        })
      }.not_to have_enqueued_job(DraftJob)
    end
  end

  describe "webhook -> sync -> classify -> draft chain" do
    it "processes a complete notification chain" do
      notification_data = {
        emailAddress: user.email,
        historyId: 12346
      }
      encoded_data = Base64.strict_encode64(notification_data.to_json)

      expect {
        post "/webhook/gmail", params: {
          message: { data: encoded_data }
        }, as: :json
      }.to have_enqueued_job(SyncJob)
    end
  end
end
