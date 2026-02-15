# frozen_string_literal: true

require "rails_helper"

RSpec.describe ClassifyJob, type: :job do
  let(:user) { create(:user) }
  let(:pipeline) { instance_double(Classification::Pipeline) }

  before do
    allow(Classification::Pipeline).to receive(:new).with(user: user).and_return(pipeline)
  end

  describe "#perform with new email data" do
    let(:payload) do
      {
        "gmail_thread_id" => "thread_123",
        "gmail_message_id" => "msg_123",
        "sender_email" => "sender@example.com",
        "sender_name" => "Sender",
        "subject" => "Test Subject",
        "snippet" => "Test snippet",
        "received_at" => Time.current.iso8601
      }
    end

    it "classifies new email data through pipeline" do
      allow(pipeline).to receive(:classify)
      # No email record yet, so can_draft? won't trigger
      allow(user.emails).to receive(:find_by).and_return(nil)

      described_class.new.perform(user.id, payload)

      expect(pipeline).to have_received(:classify).with(
        email_data: hash_including(
          gmail_thread_id: "thread_123",
          sender_email: "sender@example.com"
        )
      )
    end

    it "enqueues DraftJob when classified as needs_response" do
      allow(pipeline).to receive(:classify)
      email = create(:email, user: user,
                             gmail_thread_id: "thread_123",
                             classification: "needs_response",
                             status: "pending")

      expect {
        described_class.new.perform(user.id, payload)
      }.to have_enqueued_job(DraftJob).with(user.id, { "email_id" => email.id })
    end

    it "does not enqueue DraftJob when classified as fyi" do
      allow(pipeline).to receive(:classify)
      create(:email, user: user,
                     gmail_thread_id: "thread_123",
                     classification: "fyi",
                     status: "pending")

      expect {
        described_class.new.perform(user.id, payload)
      }.not_to have_enqueued_job(DraftJob)
    end
  end

  describe "#perform with reclassification" do
    it "reclassifies an existing email" do
      email = create(:email, user: user)
      allow(pipeline).to receive(:reclassify)

      described_class.new.perform(user.id, { "email_id" => email.id })

      expect(pipeline).to have_received(:reclassify).with(email)
    end
  end

  describe "queue" do
    it "is enqueued on the default queue" do
      expect(described_class.new.queue_name).to eq("default")
    end
  end
end
