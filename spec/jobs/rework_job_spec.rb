# frozen_string_literal: true

require "rails_helper"

RSpec.describe ReworkJob, type: :job do
  let(:user) { create(:user) }
  let(:generator) { instance_double(Drafting::DraftGenerator) }

  before do
    allow(Drafting::DraftGenerator).to receive(:new).with(user: user).and_return(generator)
  end

  describe "#perform" do
    it "reworks a drafted email with the given instruction" do
      email = create(:email, user: user, classification: "needs_response", status: "drafted")
      allow(generator).to receive(:rework)

      described_class.new.perform(user.id, { "email_id" => email.id, "instruction" => "Make it shorter" })

      expect(generator).to have_received(:rework).with(email, instruction: "Make it shorter")
    end

    it "uses last_rework_instruction when no explicit instruction given" do
      email = create(:email, user: user,
                             classification: "needs_response",
                             status: "rework_requested",
                             last_rework_instruction: "More formal tone")
      allow(generator).to receive(:rework)

      described_class.new.perform(user.id, { "email_id" => email.id })

      expect(generator).to have_received(:rework).with(email, instruction: "More formal tone")
    end

    it "uses default instruction when none available" do
      email = create(:email, user: user, classification: "needs_response", status: "drafted")
      allow(generator).to receive(:rework)

      described_class.new.perform(user.id, { "email_id" => email.id })

      expect(generator).to have_received(:rework).with(email, instruction: "Please improve this draft")
    end

    it "skips emails that are not in drafted or rework_requested status" do
      email = create(:email, user: user, classification: "needs_response", status: "sent")
      allow(generator).to receive(:rework)

      described_class.new.perform(user.id, { "email_id" => email.id })

      expect(generator).not_to have_received(:rework)
    end

    it "is enqueued on the default queue" do
      expect(described_class.new.queue_name).to eq("default")
    end
  end
end
