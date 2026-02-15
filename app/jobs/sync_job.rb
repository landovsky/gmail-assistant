# frozen_string_literal: true

class SyncJob < ApplicationJob
  queue_as :default
  retry_on StandardError, wait: :polynomially_longer, attempts: 3

  def perform(user_id)
    user = User.find(user_id)
    engine = Sync::SyncEngine.new(user: user)
    engine.sync!
  end
end
