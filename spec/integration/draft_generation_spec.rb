# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Draft Generation Integration", type: :integration do
  let(:user) { create(:user) }
  let(:gmail_client) { instance_double(Gmail::Client) }
  let(:llm) { instance_double(LlmGateway) }
  let(:draft_response) { OpenStruct.new(id: "new_draft_123") }

  before do
    %w[needs_response action_required payment_request fyi waiting outbox rework done].each_with_index do |key, i|
      create(:user_label, user: user, label_key: key, gmail_label_id: "Label_#{i}")
    end

    allow(Gmail::Client).to receive(:new).and_return(gmail_client)
    allow(LlmGateway).to receive(:new).and_return(llm)
    allow(gmail_client).to receive(:modify_message_labels)
    allow(gmail_client).to receive(:create_draft).and_return(draft_response)
    allow(gmail_client).to receive(:delete_draft)

    # Context gatherer stubs - chat_json raises so context gathering is skipped
    allow(llm).to receive(:chat_json).and_raise(LlmGateway::LlmError, "No LLM available")
    allow(gmail_client).to receive(:list_messages).and_raise(Gmail::Client::GmailApiError, "No API")

    # Stub chat as spy so we can verify calls
    allow(llm).to receive(:chat)
  end

  describe "initial draft creation" do
    it "generates draft through full pipeline" do
      email = create(:email, user: user, classification: "needs_response", status: "pending")

      allow(llm).to receive(:chat).and_return({
        content: "Dear John, Thank you for your email. I will review the document and get back to you by Friday. Best regards",
        response_text: "Dear John, Thank you for your email. I will review the document and get back to you by Friday. Best regards",
        prompt_tokens: 200,
        completion_tokens: 80,
        total_tokens: 280,
        tool_calls: nil,
        finish_reason: "stop"
      })

      generator = Drafting::DraftGenerator.new(user: user, gmail_client: gmail_client, llm_gateway: llm)
      result = generator.generate(email)

      expect(result.status).to eq("drafted")
      expect(result.draft_id).to eq("new_draft_123")
      expect(result.drafted_at).to be_present

      expect(gmail_client).to have_received(:create_draft).with(
        thread_id: email.gmail_thread_id,
        to: email.sender_email,
        subject: "Re: #{email.subject}",
        body_html: anything
      )

      expect(gmail_client).to have_received(:modify_message_labels)

      events = EmailEvent.where(gmail_thread_id: email.gmail_thread_id)
      expect(events.map(&:event_type)).to include("draft_created")
    end
  end

  describe "draft rework" do
    let(:email) do
      create(:email, user: user,
             classification: "needs_response",
             status: "drafted",
             draft_id: "old_draft_456",
             drafted_at: Time.current)
    end

    it "reworks draft based on user instruction" do
      allow(llm).to receive(:chat).and_return({
        content: "Short reply here.",
        response_text: "Short reply here.",
        prompt_tokens: 150,
        completion_tokens: 30,
        total_tokens: 180,
        tool_calls: nil,
        finish_reason: "stop"
      })

      generator = Drafting::DraftGenerator.new(user: user, gmail_client: gmail_client, llm_gateway: llm)
      result = generator.rework(email, instruction: "Make it shorter")

      expect(result.status).to eq("drafted")
      expect(result.draft_id).to eq("new_draft_123")
      expect(result.rework_count).to eq(1)
      expect(result.last_rework_instruction).to eq("Make it shorter")

      expect(gmail_client).to have_received(:delete_draft).with("old_draft_456")

      events = EmailEvent.where(gmail_thread_id: email.gmail_thread_id)
      expect(events.map(&:event_type)).to include("draft_reworked")
    end
  end

  describe "rework limit enforcement" do
    it "stops rework at 3 iterations and skips email" do
      email = create(:email, user: user,
                     classification: "needs_response",
                     status: "drafted",
                     draft_id: "draft_limit",
                     drafted_at: Time.current,
                     rework_count: 3)

      generator = Drafting::DraftGenerator.new(user: user, gmail_client: gmail_client, llm_gateway: llm)
      result = generator.rework(email, instruction: "One more try")

      expect(result.status).to eq("skipped")

      # No new LLM draft call (only the spy stub, not a real call)
      expect(llm).not_to have_received(:chat)

      expect(gmail_client).to have_received(:modify_message_labels).at_least(:once)

      events = EmailEvent.where(gmail_thread_id: email.gmail_thread_id)
      expect(events.map(&:event_type)).to include("rework_limit_reached")
    end
  end

  describe "draft contains scissors marker" do
    it "includes scissors marker in generated draft HTML" do
      email = create(:email, user: user, classification: "needs_response", status: "pending")

      allow(llm).to receive(:chat).and_return({
        content: "Reply text here",
        response_text: "Reply text here",
        prompt_tokens: 100,
        completion_tokens: 20,
        total_tokens: 120,
        tool_calls: nil,
        finish_reason: "stop"
      })

      generator = Drafting::DraftGenerator.new(user: user, gmail_client: gmail_client, llm_gateway: llm)
      generator.generate(email)

      expect(gmail_client).to have_received(:create_draft).with(
        hash_including(body_html: include("\u2702\uFE0F"))
      )
    end
  end
end
