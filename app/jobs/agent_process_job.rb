# frozen_string_literal: true

class AgentProcessJob < ApplicationJob
  queue_as :default
  retry_on StandardError, wait: :polynomially_longer, attempts: 3

  def perform(user_id, payload)
    user = User.find(user_id)
    payload = payload.symbolize_keys

    gmail_thread_id = payload[:gmail_thread_id]
    gmail_message_id = payload[:gmail_message_id]
    profile_name = payload[:profile]

    gmail_client = Gmail::Client.new(user: user)

    # Fetch the email thread
    message = gmail_client.get_message(gmail_message_id, format: "full")
    parsed = Gmail::MessageParser.parse(message)

    # Log start event
    email = user.emails.find_by(gmail_thread_id: gmail_thread_id)
    email&.log_event("agent_started", "Agent '#{profile_name}' processing started")

    # Run preprocessor
    preprocessor = select_preprocessor(profile_name)
    processed = preprocessor.process(
      subject: parsed[:subject],
      body: parsed[:body_text] || parsed[:snippet],
      headers: parsed[:headers] || {}
    )

    # Execute agent loop
    agent_loop = Agent::Loop.new(user: user, gmail_client: gmail_client)
    agent_loop.execute(
      gmail_thread_id: gmail_thread_id,
      profile_name: profile_name,
      user_message: processed[:formatted_message]
    )
  end

  private

  def select_preprocessor(profile_name)
    # Select preprocessor based on profile
    case profile_name
    when "pharmacy"
      Agent::Preprocessors::CrispPreprocessor.new
    else
      Agent::Preprocessors::DefaultPreprocessor.new
    end
  end
end
