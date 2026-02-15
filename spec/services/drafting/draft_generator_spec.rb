# frozen_string_literal: true

require "rails_helper"

RSpec.describe Drafting::DraftGenerator do
  let(:user) { create(:user) }
  let(:gmail_client) { instance_double(Gmail::Client) }
  let(:llm_gateway) { instance_double(LlmGateway) }
  let(:generator) { described_class.new(user: user, gmail_client: gmail_client, llm_gateway: llm_gateway) }

  let(:email) { create(:email, :needs_response, user: user) }

  let(:gmail_draft) { double(id: "draft_new_123") }

  before do
    # Create user labels
    %w[needs_response action_required payment_request fyi waiting outbox rework done].each_with_index do |key, i|
      create(:user_label, user: user, label_key: key, gmail_label_id: "Label_#{i}")
    end

    # Mock LLM calls
    allow(llm_gateway).to receive(:chat).and_return(
      response_text: "Hello! I'll get the report to you by Friday.\n\nBest regards,\nTest User",
      prompt_tokens: 200,
      completion_tokens: 100,
      total_tokens: 300,
      llm_call_id: 1
    )

    # Mock context gathering LLM call
    allow(llm_gateway).to receive(:chat_json).and_return(
      response_text: '["from:sender@example.com"]',
      parsed_response: ["from:sender@example.com"],
      prompt_tokens: 50,
      completion_tokens: 20,
      total_tokens: 70,
      llm_call_id: 2
    )

    # Mock Gmail operations
    allow(gmail_client).to receive(:create_draft).and_return(gmail_draft)
    allow(gmail_client).to receive(:delete_draft)
    allow(gmail_client).to receive(:modify_message_labels)
    allow(gmail_client).to receive(:list_messages).and_return(
      double(messages: nil)
    )
  end

  describe "#generate" do
    it "generates a draft and updates the email record" do
      result = generator.generate(email)

      expect(result.status).to eq("drafted")
      expect(result.draft_id).to eq("draft_new_123")
      expect(result.drafted_at).to be_present
    end

    it "calls LLM with draft model" do
      generator.generate(email)

      expect(llm_gateway).to have_received(:chat).with(
        hash_including(
          model: AppConfig.llm.draft_model,
          call_type: "draft"
        )
      )
    end

    it "creates a Gmail draft" do
      generator.generate(email)

      expect(gmail_client).to have_received(:create_draft).with(
        hash_including(
          thread_id: email.gmail_thread_id,
          to: email.sender_email,
          subject: "Re: #{email.subject}"
        )
      )
    end

    it "applies outbox label" do
      generator.generate(email)

      expect(gmail_client).to have_received(:modify_message_labels).with(
        email.gmail_message_id,
        add_label_ids: ["Label_5"] # outbox label
      )
    end

    it "logs a draft_created event" do
      generator.generate(email)

      event = EmailEvent.find_by(event_type: "draft_created")
      expect(event).to be_present
      expect(event.gmail_thread_id).to eq(email.gmail_thread_id)
    end

    it "trashes existing draft if present" do
      email.update!(draft_id: "old_draft_123")
      generator.generate(email)

      expect(gmail_client).to have_received(:delete_draft).with("old_draft_123")
    end

    context "with user instructions" do
      it "includes instructions in the LLM prompt" do
        generator.generate(email, user_instructions: "Be more formal")

        expect(llm_gateway).to have_received(:chat).with(
          hash_including(messages: array_including(
            hash_including(content: include("Be more formal"))
          ))
        )
      end
    end
  end

  describe "#rework" do
    let(:drafted_email) { create(:email, :drafted, user: user) }

    it "generates a reworked draft" do
      result = generator.rework(drafted_email, instruction: "Make it shorter")

      expect(result.status).to eq("drafted")
      expect(result.rework_count).to eq(1)
      expect(result.last_rework_instruction).to eq("Make it shorter")
    end

    it "calls LLM with rework call_type" do
      generator.rework(drafted_email, instruction: "More formal")

      expect(llm_gateway).to have_received(:chat).with(
        hash_including(call_type: "rework")
      )
    end

    it "trashes old draft and creates new one" do
      old_draft_id = drafted_email.draft_id
      generator.rework(drafted_email, instruction: "Shorter")

      expect(gmail_client).to have_received(:delete_draft).with(old_draft_id)
      expect(gmail_client).to have_received(:create_draft)
    end

    it "logs a draft_reworked event" do
      generator.rework(drafted_email, instruction: "Better")

      event = EmailEvent.find_by(event_type: "draft_reworked")
      expect(event).to be_present
    end

    context "when rework limit is reached" do
      let(:maxed_email) { create(:email, :drafted, user: user, rework_count: 3) }

      it "marks email as skipped" do
        result = generator.rework(maxed_email, instruction: "Fourth attempt")

        expect(result.status).to eq("skipped")
      end

      it "does not call LLM" do
        generator.rework(maxed_email, instruction: "Fourth attempt")

        expect(llm_gateway).not_to have_received(:chat)
      end

      it "removes outbox label and adds action_required label" do
        generator.rework(maxed_email, instruction: "Fourth attempt")

        expect(gmail_client).to have_received(:modify_message_labels).at_least(:once)
      end
    end
  end
end
