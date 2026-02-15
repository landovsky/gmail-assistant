# frozen_string_literal: true

require "rails_helper"

RSpec.describe DraftJob, type: :job do
  let(:user) { create(:user) }
  let(:generator) { instance_double(Drafting::DraftGenerator) }

  before do
    allow(Drafting::DraftGenerator).to receive(:new).with(user: user).and_return(generator)
  end

  describe "#perform" do
    it "generates a draft for a pending needs_response email" do
      email = create(:email, user: user, classification: "needs_response", status: "pending")
      allow(generator).to receive(:generate)

      described_class.new.perform(user.id, { "email_id" => email.id })

      expect(generator).to have_received(:generate).with(email, user_instructions: nil)
    end

    it "passes user instructions when provided" do
      email = create(:email, user: user, classification: "needs_response", status: "pending")
      allow(generator).to receive(:generate)

      described_class.new.perform(user.id, { "email_id" => email.id, "instructions" => "Be formal" })

      expect(generator).to have_received(:generate).with(email, user_instructions: "Be formal")
    end

    it "skips emails that cannot be drafted" do
      email = create(:email, user: user, classification: "fyi", status: "archived")
      allow(generator).to receive(:generate)

      described_class.new.perform(user.id, { "email_id" => email.id })

      expect(generator).not_to have_received(:generate)
    end

    it "is enqueued on the default queue" do
      expect(described_class.new.queue_name).to eq("default")
    end
  end
end
