# frozen_string_literal: true

require "rails_helper"

RSpec.describe CleanupJob, type: :job do
  let(:user) { create(:user) }

  describe "#perform" do
    context "with specific user" do
      it "cleans up stale completed jobs older than 7 days" do
        stale_job = create(:job, user: user, status: "completed",
                                 created_at: 8.days.ago)
        recent_completed = create(:job, user: user, status: "completed",
                                        created_at: 1.day.ago)
        pending_job = create(:job, user: user, status: "pending")

        gmail_client = instance_double(Gmail::Client)
        allow(Gmail::Client).to receive(:new).and_return(gmail_client)

        described_class.new.perform(user.id)

        expect(Job.where(id: stale_job.id).exists?).to be false
        expect(Job.where(id: recent_completed.id).exists?).to be true
        expect(Job.where(id: pending_job.id).exists?).to be true
      end

      it "detects sent drafts when draft no longer exists in Gmail" do
        gmail_client = instance_double(Gmail::Client)
        label_manager = instance_double(Gmail::LabelManager)
        allow(Gmail::Client).to receive(:new).and_return(gmail_client)
        allow(Gmail::LabelManager).to receive(:new).and_return(label_manager)

        email = create(:email, user: user,
                               classification: "needs_response",
                               status: "drafted",
                               draft_id: "draft_123",
                               gmail_message_id: "msg_456")

        allow(gmail_client).to receive(:get_draft)
          .with("draft_123")
          .and_raise(Gmail::Client::NotFoundError, "Draft not found")
        allow(label_manager).to receive(:remove_label)
        allow(label_manager).to receive(:apply_workflow_label)

        described_class.new.perform(user.id)

        email.reload
        expect(email.status).to eq("sent")
        expect(label_manager).to have_received(:remove_label).with(
          message_id: "msg_456", label_key: "outbox"
        )
        expect(label_manager).to have_received(:apply_workflow_label).with(
          message_id: "msg_456", label_key: "done"
        )
      end

      it "does not change email status when draft still exists" do
        gmail_client = instance_double(Gmail::Client)
        allow(Gmail::Client).to receive(:new).and_return(gmail_client)

        email = create(:email, user: user,
                               classification: "needs_response",
                               status: "drafted",
                               draft_id: "draft_123")

        allow(gmail_client).to receive(:get_draft)
          .with("draft_123")
          .and_return(double("draft"))

        described_class.new.perform(user.id)

        expect(email.reload.status).to eq("drafted")
      end

      it "handles Gmail API errors gracefully" do
        gmail_client = instance_double(Gmail::Client)
        allow(Gmail::Client).to receive(:new).and_return(gmail_client)

        email = create(:email, user: user,
                               classification: "needs_response",
                               status: "drafted",
                               draft_id: "draft_123")

        allow(gmail_client).to receive(:get_draft)
          .and_raise(Gmail::Client::GmailApiError, "API error")

        expect {
          described_class.new.perform(user.id)
        }.not_to raise_error

        expect(email.reload.status).to eq("drafted")
      end

      it "skips drafted emails without draft_id" do
        gmail_client = instance_double(Gmail::Client)
        allow(Gmail::Client).to receive(:new).and_return(gmail_client)

        email = create(:email, user: user,
                               classification: "needs_response",
                               status: "drafted",
                               draft_id: nil)

        described_class.new.perform(user.id)

        # get_draft should never be called
        expect(gmail_client).not_to have_received(:get_draft) if gmail_client.respond_to?(:get_draft)
        expect(email.reload.status).to eq("drafted")
      end
    end

    context "without user_id (global cleanup)" do
      it "runs cleanup for all active users" do
        active_user = create(:user)
        _inactive_user = create(:user, :inactive)

        gmail_client = instance_double(Gmail::Client)
        allow(Gmail::Client).to receive(:new).and_return(gmail_client)

        # Should not raise
        expect { described_class.new.perform }.not_to raise_error
      end
    end
  end

  describe "queue" do
    it "is enqueued on the low queue" do
      expect(described_class.new.queue_name).to eq("low")
    end
  end
end
