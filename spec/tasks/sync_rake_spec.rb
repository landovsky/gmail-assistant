# frozen_string_literal: true

require "rails_helper"
require "rake"

RSpec.describe "sync rake tasks" do
  before(:all) do
    Rails.application.load_tasks unless Rake::Task.task_defined?("sync:full")
  end

  describe "sync:full" do
    it "is defined" do
      expect(Rake::Task.task_defined?("sync:full")).to be true
    end
  end

  describe "sync:reset_and_sync" do
    it "is defined" do
      expect(Rake::Task.task_defined?("sync:reset_and_sync")).to be true
    end
  end
end
