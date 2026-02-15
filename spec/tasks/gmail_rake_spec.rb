# frozen_string_literal: true

require "rails_helper"
require "rake"

RSpec.describe "gmail rake tasks" do
  before(:all) do
    Rails.application.load_tasks unless Rake::Task.task_defined?("gmail:cleanup_labels")
  end

  describe "gmail:cleanup_labels" do
    it "is defined" do
      expect(Rake::Task.task_defined?("gmail:cleanup_labels")).to be true
    end
  end

  describe "gmail:cleanup_drafts" do
    it "is defined" do
      expect(Rake::Task.task_defined?("gmail:cleanup_drafts")).to be true
    end
  end
end
