# frozen_string_literal: true

require "rails_helper"

RSpec.describe SyncState do
  describe "validations" do
    it { is_expected.to validate_presence_of(:last_history_id) }

    it "enforces uniqueness of user_id" do
      user = create(:user) # This creates sync_state via callback
      duplicate = build(:sync_state, user: user)
      expect(duplicate).not_to be_valid
    end
  end

  describe "associations" do
    it { is_expected.to belong_to(:user) }
  end

  describe "#watch_active?" do
    it "returns true when watch has not expired" do
      state = build(:sync_state, watch_expiration: 1.day.from_now)
      expect(state.watch_active?).to be true
    end

    it "returns false when watch has expired" do
      state = build(:sync_state, watch_expiration: 1.day.ago)
      expect(state.watch_active?).to be false
    end

    it "returns false when watch_expiration is nil" do
      state = build(:sync_state, watch_expiration: nil)
      expect(state.watch_active?).to be false
    end
  end

  describe "#needs_full_sync?" do
    it "returns true when history_id is 0" do
      state = build(:sync_state, last_history_id: "0")
      expect(state.needs_full_sync?).to be true
    end

    it "returns false when history_id is non-zero" do
      state = build(:sync_state, last_history_id: "12345")
      expect(state.needs_full_sync?).to be false
    end
  end

  describe "#update_history_id!" do
    it "updates history ID and sync timestamp" do
      user = create(:user)
      state = user.sync_state
      state.update_history_id!("67890")

      expect(state.last_history_id).to eq("67890")
      expect(state.last_sync_at).to be_present
    end
  end
end
