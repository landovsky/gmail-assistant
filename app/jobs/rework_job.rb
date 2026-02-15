# frozen_string_literal: true

class ReworkJob < ApplicationJob
  queue_as :default
  retry_on StandardError, wait: :polynomially_longer, attempts: 3

  def perform(user_id, payload)
    user = User.find(user_id)
    payload = payload.symbolize_keys
    email = user.emails.find(payload[:email_id])

    return unless email.status.in?(%w[drafted rework_requested])

    instruction = payload[:instruction] || email.last_rework_instruction || "Please improve this draft"

    generator = Drafting::DraftGenerator.new(user: user)
    generator.rework(email, instruction: instruction)
  end
end
