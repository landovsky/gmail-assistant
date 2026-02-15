# frozen_string_literal: true

require "rails_helper"

RSpec.describe Gmail::MessageParser do
  describe ".parse" do
    let(:message) do
      headers = [
        Google::Apis::GmailV1::MessagePartHeader.new(name: "From", value: "John Doe <john@example.com>"),
        Google::Apis::GmailV1::MessagePartHeader.new(name: "Subject", value: "Test Subject"),
        Google::Apis::GmailV1::MessagePartHeader.new(name: "Date", value: "Sat, 15 Feb 2026 10:00:00 +0000")
      ]

      body_text = Google::Apis::GmailV1::MessagePartBody.new(
        data: Base64.urlsafe_encode64("Hello, this is plain text.")
      )
      body_html = Google::Apis::GmailV1::MessagePartBody.new(
        data: Base64.urlsafe_encode64("<p>Hello, this is HTML.</p>")
      )

      parts = [
        Google::Apis::GmailV1::MessagePart.new(mime_type: "text/plain", body: body_text),
        Google::Apis::GmailV1::MessagePart.new(mime_type: "text/html", body: body_html)
      ]

      payload = Google::Apis::GmailV1::MessagePart.new(
        mime_type: "multipart/alternative",
        headers: headers,
        parts: parts
      )

      Google::Apis::GmailV1::Message.new(
        id: "msg_123",
        thread_id: "thread_456",
        snippet: "Hello, this is...",
        label_ids: %w[INBOX UNREAD],
        payload: payload
      )
    end

    it "extracts all fields from a Gmail message" do
      result = described_class.parse(message)

      expect(result[:gmail_message_id]).to eq("msg_123")
      expect(result[:gmail_thread_id]).to eq("thread_456")
      expect(result[:sender_email]).to eq("john@example.com")
      expect(result[:sender_name]).to eq("John Doe")
      expect(result[:subject]).to eq("Test Subject")
      expect(result[:snippet]).to eq("Hello, this is...")
      expect(result[:body_text]).to eq("Hello, this is plain text.")
      expect(result[:body_html]).to eq("<p>Hello, this is HTML.</p>")
    end

    it "handles sender with email only (no display name)" do
      headers = [
        Google::Apis::GmailV1::MessagePartHeader.new(name: "From", value: "noreply@example.com")
      ]
      payload = Google::Apis::GmailV1::MessagePart.new(
        mime_type: "text/plain",
        headers: headers,
        body: Google::Apis::GmailV1::MessagePartBody.new(data: nil)
      )
      msg = Google::Apis::GmailV1::Message.new(
        id: "msg_1", thread_id: "t_1", payload: payload
      )

      result = described_class.parse(msg)
      expect(result[:sender_email]).to eq("noreply@example.com")
      expect(result[:sender_name]).to be_nil
    end
  end
end
