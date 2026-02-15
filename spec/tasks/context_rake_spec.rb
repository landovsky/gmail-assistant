# frozen_string_literal: true

require "rails_helper"
require "rake"

RSpec.describe "context rake tasks" do
  before(:all) do
    Rails.application.load_tasks unless Rake::Task.task_defined?("context:debug")
  end

  describe "context:debug" do
    it "is defined" do
      expect(Rake::Task.task_defined?("context:debug")).to be true
    end
  end
end
