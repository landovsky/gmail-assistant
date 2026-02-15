# frozen_string_literal: true

class DraftJob < ApplicationJob
  queue_as :default
  retry_on StandardError, wait: :polynomially_longer, attempts: 3

  def perform(user_id, payload)
    user = User.find(user_id)
    payload = payload.symbolize_keys
    email = user.emails.find(payload[:email_id])

    return unless email.can_draft? || email.status == "pending"

    generator = Drafting::DraftGenerator.new(user: user)
    generator.generate(email, user_instructions: payload[:instructions])
  end
end
