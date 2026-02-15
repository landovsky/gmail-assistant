# frozen_string_literal: true

require "webrick"
require "googleauth"
require "googleauth/stores/file_token_store"

module Gmail
  # Wrapper around the Google Gmail API v1 client.
  # Handles authentication, token refresh, and provides domain-specific methods.
  class Client
    class GmailApiError < StandardError; end
    class AuthenticationError < GmailApiError; end
    class NotFoundError < GmailApiError; end

    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"].freeze

    def initialize(user: nil)
      @user = user
      @service = build_service
    end

    # === Messages ===

    def get_message(message_id, format: "full")
      @service.get_user_message("me", message_id, format: format)
    rescue Google::Apis::ClientError => e
      raise NotFoundError, "Message #{message_id} not found" if e.status_code == 404

      raise GmailApiError, "Failed to get message: #{e.message}"
    end

    def list_messages(query: nil, max_results: 100, label_ids: nil, page_token: nil)
      @service.list_user_messages(
        "me",
        q: query,
        max_results: max_results,
        label_ids: label_ids,
        page_token: page_token
      )
    rescue Google::Apis::ClientError => e
      raise GmailApiError, "Failed to list messages: #{e.message}"
    end

    # === Threads ===

    def get_thread(thread_id, format: "full")
      @service.get_user_thread("me", thread_id, format: format)
    rescue Google::Apis::ClientError => e
      raise NotFoundError, "Thread #{thread_id} not found" if e.status_code == 404

      raise GmailApiError, "Failed to get thread: #{e.message}"
    end

    # === Labels ===

    def list_labels
      response = @service.list_user_labels("me")
      response.labels || []
    rescue Google::Apis::ClientError => e
      raise GmailApiError, "Failed to list labels: #{e.message}"
    end

    def create_label(name, label_list_visibility: "labelShow", message_list_visibility: "show")
      label = Google::Apis::GmailV1::Label.new(
        name: name,
        label_list_visibility: label_list_visibility,
        message_list_visibility: message_list_visibility
      )
      @service.create_user_label("me", label)
    rescue Google::Apis::ClientError => e
      raise GmailApiError, "Failed to create label '#{name}': #{e.message}"
    end

    def modify_message_labels(message_id, add_label_ids: [], remove_label_ids: [])
      request = Google::Apis::GmailV1::ModifyMessageRequest.new(
        add_label_ids: add_label_ids,
        remove_label_ids: remove_label_ids
      )
      @service.modify_message("me", message_id, request)
    rescue Google::Apis::ClientError => e
      raise GmailApiError, "Failed to modify labels: #{e.message}"
    end

    # === Drafts ===

    def create_draft(thread_id:, to:, subject:, body_html:, in_reply_to: nil, references: nil)
      message = build_mime_message(to: to, subject: subject, body_html: body_html,
                                   thread_id: thread_id, in_reply_to: in_reply_to, references: references)

      draft = Google::Apis::GmailV1::Draft.new(
        message: Google::Apis::GmailV1::Message.new(
          thread_id: thread_id,
          raw: Base64.urlsafe_encode64(message)
        )
      )

      @service.create_user_draft("me", draft)
    rescue Google::Apis::ClientError => e
      raise GmailApiError, "Failed to create draft: #{e.message}"
    end

    def delete_draft(draft_id)
      @service.delete_user_draft("me", draft_id)
    rescue Google::Apis::ClientError => e
      raise NotFoundError, "Draft #{draft_id} not found" if e.status_code == 404

      raise GmailApiError, "Failed to delete draft: #{e.message}"
    end

    def get_draft(draft_id)
      @service.get_user_draft("me", draft_id)
    rescue Google::Apis::ClientError => e
      raise NotFoundError, "Draft #{draft_id} not found" if e.status_code == 404

      raise GmailApiError, "Failed to get draft: #{e.message}"
    end

    # === History ===

    def list_history(start_history_id:, history_types: nil, max_results: 100)
      @service.list_user_histories(
        "me",
        start_history_id: start_history_id,
        history_types: history_types,
        max_results: max_results
      )
    rescue Google::Apis::ClientError => e
      if e.status_code == 404
        # History ID is too old, need full sync
        raise NotFoundError, "History ID #{start_history_id} expired, full sync required"
      end

      raise GmailApiError, "Failed to list history: #{e.message}"
    end

    # === Watch (Pub/Sub) ===

    def watch(topic_name:, label_ids: ["INBOX"])
      request = Google::Apis::GmailV1::WatchRequest.new(
        topic_name: topic_name,
        label_ids: label_ids
      )
      @service.watch_user("me", request)
    rescue Google::Apis::ClientError => e
      raise GmailApiError, "Failed to set up watch: #{e.message}"
    end

    def stop_watch
      @service.stop_user("me")
    rescue Google::Apis::ClientError => e
      raise GmailApiError, "Failed to stop watch: #{e.message}"
    end

    # === Profile ===

    def get_profile
      @service.get_user_profile("me")
    rescue Google::Apis::ClientError => e
      raise GmailApiError, "Failed to get profile: #{e.message}"
    end

    private

    def build_service
      service = Google::Apis::GmailV1::GmailService.new
      service.authorization = build_authorization
      service
    end

    def build_authorization
      config = AppConfig.auth
      credentials_file = Rails.root.join(config.credentials_file)
      token_file = Rails.root.join(config.token_file)

      unless File.exist?(credentials_file)
        raise AuthenticationError, "Credentials file not found: #{credentials_file}"
      end

      authorizer = Google::Auth::UserAuthorizer.new(
        Google::Auth::ClientId.from_file(credentials_file.to_s),
        SCOPES,
        Google::Auth::Stores::FileTokenStore.new(file: token_file.to_s)
      )

      # Try to get existing credentials
      credentials = authorizer.get_credentials("default")
      return credentials if credentials

      # No token file or expired token - trigger OAuth consent flow
      Rails.logger.info("No valid credentials found, triggering OAuth consent flow...")

      # Use localhost callback server for authorization
      callback_uri = "http://localhost:8080/"
      url = authorizer.get_authorization_url(base_url: callback_uri)

      Rails.logger.info("Starting local callback server on port 8080...")

      # Start a simple web server to receive the OAuth callback
      code = nil
      server = WEBrick::HTTPServer.new(Port: 8080, AccessLog: [], Logger: WEBrick::Log.new("/dev/null"))

      server.mount_proc "/" do |req, res|
        code = req.query["code"]
        res.body = <<~HTML
          <html>
          <head><title>Authorization Successful</title></head>
          <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1>✓ Authorization Successful!</h1>
            <p>You can close this window and return to the terminal.</p>
          </body>
          </html>
        HTML
        server.shutdown
      end

      puts "\n" + "=" * 80
      puts "GMAIL AUTHORIZATION REQUIRED"
      puts "=" * 80
      puts "\nOpening browser for Google OAuth consent..."
      puts "\nIf your browser doesn't open automatically, visit:\n"
      puts "   #{url}\n"
      puts "=" * 80 + "\n"

      # Try to open the browser automatically
      begin
        if RbConfig::CONFIG["host_os"] =~ /darwin/
          system("open", url)
        elsif RbConfig::CONFIG["host_os"] =~ /linux/
          system("xdg-open", url)
        elsif RbConfig::CONFIG["host_os"] =~ /mswin|mingw|cygwin/
          system("start", url)
        end
      rescue StandardError => e
        Rails.logger.warn("Could not open browser automatically: #{e.message}")
      end

      # Wait for callback
      server.start

      unless code
        raise AuthenticationError, "No authorization code received from OAuth callback"
      end

      credentials = authorizer.get_and_store_credentials_from_code(
        user_id: "default",
        code: code,
        base_url: callback_uri
      )

      Rails.logger.info("✓ Authorization successful! Credentials saved to #{token_file}")

      credentials
    rescue StandardError => e
      raise AuthenticationError, "Authentication failed: #{e.message}" unless e.is_a?(AuthenticationError)

      raise
    end

    def build_mime_message(to:, subject:, body_html:, thread_id: nil, in_reply_to: nil, references: nil)
      headers = []
      headers << "To: #{to}"
      headers << "Subject: #{subject}"
      headers << "Content-Type: text/html; charset=UTF-8"
      headers << "In-Reply-To: #{in_reply_to}" if in_reply_to
      headers << "References: #{references}" if references
      headers << ""
      headers << body_html

      headers.join("\r\n")
    end
  end
end
