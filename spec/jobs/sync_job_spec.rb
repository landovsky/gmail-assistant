# frozen_string_literal: true

require "rails_helper"

RSpec.describe SyncJob, type: :job do
  let(:user) { create(:user) }

  describe "#perform" do
    it "creates a SyncEngine and calls sync!" do
      engine = instance_double(Sync::SyncEngine)
      allow(Sync::SyncEngine).to receive(:new).with(user: user).and_return(engine)
      allow(engine).to receive(:sync!)

      described_class.new.perform(user.id)

      expect(engine).to have_received(:sync!)
    end

    it "is enqueued on the default queue" do
      expect(described_class.new.queue_name).to eq("default")
    end

    it "raises for unknown user (triggers retry)" do
      expect {
        described_class.new.perform(-1)
      }.to raise_error(ActiveRecord::RecordNotFound)
    end
  end
end
