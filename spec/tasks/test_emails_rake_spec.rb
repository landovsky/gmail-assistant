# frozen_string_literal: true

require "rails_helper"
require "rake"

RSpec.describe "test_emails rake tasks" do
  before(:all) do
    Rails.application.load_tasks unless Rake::Task.task_defined?("test_emails:send")
  end

  describe "test_emails:send" do
    it "is defined" do
      expect(Rake::Task.task_defined?("test_emails:send")).to be true
    end
  end

  describe "test_emails:preview" do
    it "is defined" do
      expect(Rake::Task.task_defined?("test_emails:preview")).to be true
    end

    it "outputs a test email preview" do
      expect {
        Rake::Task["test_emails:preview"].invoke("needs_response", "formal")
      }.to output(/Test Email Preview/).to_stdout
    ensure
      Rake::Task["test_emails:preview"].reenable
    end
  end
end
