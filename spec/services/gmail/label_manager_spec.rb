# frozen_string_literal: true

require "rails_helper"

RSpec.describe Gmail::LabelManager do
  let(:user) { create(:user) }
  let(:gmail_client) { instance_double(Gmail::Client) }
  let(:manager) { described_class.new(user: user, gmail_client: gmail_client) }

  describe "#ensure_labels!" do
    let(:existing_labels) do
      [
        double(id: "Label_1", name: "GMA/Needs Response"),
        double(id: "Label_2", name: "GMA/FYI")
      ]
    end

    before do
      allow(gmail_client).to receive(:list_labels).and_return(existing_labels)
      allow(gmail_client).to receive(:create_label).and_return(
        double(id: "Label_new", name: "GMA/New")
      )
    end

    it "creates missing labels and maps all in the database" do
      manager.ensure_labels!

      expect(user.user_labels.count).to eq(Gmail::LabelManager::STANDARD_LABELS.count)
      expect(user.label_for("needs_response")).to be_present
      expect(user.label_for("fyi")).to be_present
    end

    it "does not create labels that already exist in Gmail" do
      manager.ensure_labels!

      # should have created 6 labels (8 standard - 2 existing = 6 new)
      expect(gmail_client).to have_received(:create_label).exactly(6).times
    end
  end

  describe "#apply_classification_label" do
    before do
      create(:user_label, user: user, label_key: "needs_response", gmail_label_id: "L_NR")
      create(:user_label, user: user, label_key: "fyi", gmail_label_id: "L_FYI")
      create(:user_label, user: user, label_key: "waiting", gmail_label_id: "L_WAIT")
      allow(gmail_client).to receive(:modify_message_labels)
    end

    it "adds the classification label and removes others" do
      manager.apply_classification_label(message_id: "msg_1", classification: "needs_response")

      expect(gmail_client).to have_received(:modify_message_labels).with(
        "msg_1",
        add_label_ids: ["L_NR"],
        remove_label_ids: contain_exactly("L_FYI", "L_WAIT")
      )
    end
  end

  describe "#apply_workflow_label" do
    before do
      create(:user_label, user: user, label_key: "outbox", gmail_label_id: "L_OUTBOX")
      allow(gmail_client).to receive(:modify_message_labels)
    end

    it "adds the workflow label" do
      manager.apply_workflow_label(message_id: "msg_1", label_key: "outbox")

      expect(gmail_client).to have_received(:modify_message_labels).with(
        "msg_1",
        add_label_ids: ["L_OUTBOX"]
      )
    end
  end

  describe "#remove_label" do
    before do
      create(:user_label, user: user, label_key: "rework", gmail_label_id: "L_REWORK")
      allow(gmail_client).to receive(:modify_message_labels)
    end

    it "removes the specified label" do
      manager.remove_label(message_id: "msg_1", label_key: "rework")

      expect(gmail_client).to have_received(:modify_message_labels).with(
        "msg_1",
        remove_label_ids: ["L_REWORK"]
      )
    end
  end
end
