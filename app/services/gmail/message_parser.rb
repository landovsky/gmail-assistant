# frozen_string_literal: true

module Gmail
  # Parses raw Gmail API message objects into structured data
  # suitable for creating/updating Email records.
  class MessageParser
    def self.parse(message)
      new(message).parse
    end

    def initialize(message)
      @message = message
      @headers = extract_headers
    end

    def parse
      {
        gmail_message_id: @message.id,
        gmail_thread_id: @message.thread_id,
        sender_email: extract_sender_email,
        sender_name: extract_sender_name,
        subject: extract_subject,
        snippet: @message.snippet,
        received_at: extract_date,
        label_ids: @message.label_ids&.join(","),
        body_text: extract_body_text,
        body_html: extract_body_html
      }
    end

    private

    def extract_headers
      return {} unless @message.payload&.headers

      @message.payload.headers.each_with_object({}) do |header, hash|
        hash[header.name.downcase] = header.value
      end
    end

    def extract_sender_email
      from = @headers["from"] || ""
      match = from.match(/<([^>]+)>/)
      match ? match[1] : from.strip
    end

    def extract_sender_name
      from = @headers["from"] || ""
      match = from.match(/^(.+?)\s*</)
      match ? match[1].strip.delete('"') : nil
    end

    def extract_subject
      subject = @headers["subject"] || ""
      # Remove Re: Fwd: prefixes for normalization (keep original in raw)
      subject.strip
    end

    def extract_date
      date_str = @headers["date"]
      return Time.current unless date_str

      Time.zone.parse(date_str)
    rescue ArgumentError
      Time.current
    end

    def extract_body_text
      extract_body_part("text/plain")
    end

    def extract_body_html
      extract_body_part("text/html")
    end

    def extract_body_part(mime_type)
      return nil unless @message.payload

      # Check if the payload itself is the right type
      if @message.payload.mime_type == mime_type && @message.payload.body&.data
        return decode_body(@message.payload.body.data)
      end

      # Search in parts
      find_in_parts(@message.payload.parts, mime_type)
    end

    def find_in_parts(parts, mime_type)
      return nil unless parts

      parts.each do |part|
        if part.mime_type == mime_type && part.body&.data
          return decode_body(part.body.data)
        end

        # Recurse into nested parts (multipart/alternative, etc.)
        if part.parts
          result = find_in_parts(part.parts, mime_type)
          return result if result
        end
      end

      nil
    end

    def decode_body(data)
      Base64.urlsafe_decode64(data).force_encoding("UTF-8")
    rescue ArgumentError
      data
    end
  end
end
