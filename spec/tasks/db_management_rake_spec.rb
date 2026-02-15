# frozen_string_literal: true

require "rails_helper"
require "rake"

RSpec.describe "db_management rake tasks" do
  before(:all) do
    Rails.application.load_tasks unless Rake::Task.task_defined?("db_management:reset")
  end

  describe "db_management:reset" do
    it "is defined" do
      expect(Rake::Task.task_defined?("db_management:reset")).to be true
    end

    it "deletes transient data while preserving users" do
      user = create(:user)
      create(:user_label, user: user, label_key: "needs_response", gmail_label_id: "Label_1")
      email = create(:email, user: user)
      EmailEvent.create!(user: user, gmail_thread_id: email.gmail_thread_id, event_type: "classified")

      expect { Rake::Task["db_management:reset"].invoke }.to output(/Deleted transient data/).to_stdout

      expect(User.count).to eq(1)
      expect(UserLabel.count).to eq(1)
      expect(Email.count).to eq(0)
      expect(EmailEvent.count).to eq(0)
    ensure
      Rake::Task["db_management:reset"].reenable
    end
  end

  describe "db_management:stats" do
    it "is defined" do
      expect(Rake::Task.task_defined?("db_management:stats")).to be true
    end

    it "displays database statistics" do
      create(:user)
      expect { Rake::Task["db_management:stats"].invoke }.to output(/Database Statistics/).to_stdout
    ensure
      Rake::Task["db_management:stats"].reenable
    end
  end
end
