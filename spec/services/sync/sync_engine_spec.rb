# frozen_string_literal: true

require "rails_helper"

RSpec.describe Sync::SyncEngine do
  let(:user) { create(:user) }
  let(:gmail_client) { instance_double(Gmail::Client) }
  let(:engine) { described_class.new(user: user, gmail_client: gmail_client) }

  before do
    %w[needs_response action_required payment_request fyi waiting outbox rework done].each_with_index do |key, i|
      create(:user_label, user: user, label_key: key, gmail_label_id: "Label_#{i}")
    end
  end

  describe "#sync!" do
    context "when needs full sync (history_id is 0)" do
      before do
        allow(gmail_client).to receive(:list_messages).and_return(
          double(messages: [double(id: "msg_1"), double(id: "msg_2")])
        )
        allow(gmail_client).to receive(:get_message).and_return(
          build_gmail_message("msg_1", "thread_1")
        )
        allow(gmail_client).to receive(:get_profile).and_return(
          double(history_id: 12345)
        )
      end

      it "performs full sync and updates history ID" do
        engine.sync!

        expect(user.sync_state.reload.last_history_id).to eq("12345")
        expect(Job.where(job_type: "classify").count).to be >= 1
      end
    end

    context "when incremental sync" do
      before do
        user.sync_state.update!(last_history_id: "100")
      end

      it "uses History API for incremental sync" do
        history_response = double(
          history: [],
          history_id: "200"
        )
        allow(gmail_client).to receive(:list_history).and_return(history_response)

        engine.sync!

        expect(user.sync_state.reload.last_history_id).to eq("200")
      end

      it "falls back to full sync when history expired" do
        allow(gmail_client).to receive(:list_history)
          .and_raise(Gmail::Client::NotFoundError, "History expired")
        allow(gmail_client).to receive(:list_messages).and_return(double(messages: nil))
        allow(gmail_client).to receive(:get_profile).and_return(double(history_id: 300))

        engine.sync!

        expect(user.sync_state.reload.last_history_id).to eq("300")
      end
    end
  end

  # Helper to build a mock Gmail message
  def build_gmail_message(msg_id, thread_id)
    headers = [
      Google::Apis::GmailV1::MessagePartHeader.new(name: "From", value: "sender@example.com"),
      Google::Apis::GmailV1::MessagePartHeader.new(name: "Subject", value: "Test"),
      Google::Apis::GmailV1::MessagePartHeader.new(name: "Date", value: Time.current.rfc2822)
    ]
    payload = Google::Apis::GmailV1::MessagePart.new(
      mime_type: "text/plain",
      headers: headers,
      body: Google::Apis::GmailV1::MessagePartBody.new(data: nil)
    )
    Google::Apis::GmailV1::Message.new(
      id: msg_id,
      thread_id: thread_id,
      snippet: "Test snippet",
      label_ids: ["INBOX"],
      payload: payload
    )
  end
end
