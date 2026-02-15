# frozen_string_literal: true

require "rails_helper"

RSpec.describe User do
  describe "validations" do
    subject { build(:user) }

    it { is_expected.to validate_presence_of(:email) }
    it { is_expected.to validate_uniqueness_of(:email) }
    it { is_expected.to allow_value("test@example.com").for(:email) }
    it { is_expected.not_to allow_value("invalid-email").for(:email) }
  end

  describe "associations" do
    it { is_expected.to have_many(:emails).dependent(:destroy) }
    it { is_expected.to have_many(:user_labels).dependent(:destroy) }
    it { is_expected.to have_many(:user_settings).dependent(:destroy) }
    it { is_expected.to have_one(:sync_state).dependent(:destroy) }
    it { is_expected.to have_many(:jobs).dependent(:destroy) }
    it { is_expected.to have_many(:email_events).dependent(:destroy) }
    it { is_expected.to have_many(:llm_calls).dependent(:nullify) }
    it { is_expected.to have_many(:agent_runs).dependent(:destroy) }
  end

  describe "callbacks" do
    it "creates a sync_state after create" do
      user = create(:user)
      expect(user.sync_state).to be_present
      expect(user.sync_state.last_history_id).to eq("0")
    end
  end

  describe "scopes" do
    it ".active returns only active users" do
      active = create(:user, is_active: true)
      create(:user, :inactive)
      expect(described_class.active).to eq([active])
    end

    it ".onboarded returns users with onboarded_at set" do
      onboarded = create(:user, :onboarded)
      create(:user)
      expect(described_class.onboarded).to eq([onboarded])
    end
  end

  describe "#onboarded?" do
    it "returns true when onboarded_at is present" do
      user = build(:user, :onboarded)
      expect(user.onboarded?).to be true
    end

    it "returns false when onboarded_at is nil" do
      user = build(:user)
      expect(user.onboarded?).to be false
    end
  end

  describe "#setting_for" do
    it "returns parsed JSON value for a setting" do
      user = create(:user)
      create(:user_setting, user: user, key: "test", value: '{"foo": "bar"}')
      expect(user.setting_for("test")).to eq({ "foo" => "bar" })
    end

    it "returns nil for missing setting" do
      user = create(:user)
      expect(user.setting_for("nonexistent")).to be_nil
    end
  end

  describe "#update_setting" do
    it "creates a new setting" do
      user = create(:user)
      user.update_setting("test_key", { foo: "bar" })
      expect(user.setting_for("test_key")).to eq({ "foo" => "bar" })
    end

    it "updates an existing setting" do
      user = create(:user)
      user.update_setting("test_key", "old")
      user.update_setting("test_key", "new")
      expect(user.user_settings.where(key: "test_key").count).to eq(1)
      expect(user.setting_for("test_key")).to eq("new")
    end
  end

  describe "#label_for" do
    it "returns the label for a given key" do
      user = create(:user)
      label = create(:user_label, user: user, label_key: "needs_response")
      expect(user.label_for("needs_response")).to eq(label)
    end

    it "returns nil for missing label" do
      user = create(:user)
      expect(user.label_for("nonexistent")).to be_nil
    end
  end
end
