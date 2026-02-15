# frozen_string_literal: true

require "rails_helper"

RSpec.describe UserLabel do
  describe "validations" do
    subject { build(:user_label) }

    it { is_expected.to validate_presence_of(:label_key) }
    it { is_expected.to validate_uniqueness_of(:label_key).scoped_to(:user_id) }
    it { is_expected.to validate_presence_of(:gmail_label_id) }
    it { is_expected.to validate_presence_of(:gmail_label_name) }
  end

  describe "associations" do
    it { is_expected.to belong_to(:user) }
  end

  describe "scopes" do
    let!(:user) { create(:user) }

    it ".for_key returns labels matching a key" do
      label = create(:user_label, user: user, label_key: "needs_response")
      create(:user_label, user: user, label_key: "fyi")

      expect(described_class.for_key("needs_response")).to contain_exactly(label)
    end

    it ".classification_labels returns classification labels" do
      nr = create(:user_label, user: user, label_key: "needs_response")
      create(:user_label, user: user, label_key: "outbox")

      expect(described_class.classification_labels).to contain_exactly(nr)
    end
  end
end
