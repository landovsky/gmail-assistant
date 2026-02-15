# frozen_string_literal: true

require "rails_helper"
require "rake"

RSpec.describe "classification rake tasks" do
  before(:all) do
    Rails.application.load_tasks unless Rake::Task.task_defined?("classification:debug")
  end

  describe "classification:debug" do
    it "is defined" do
      expect(Rake::Task.task_defined?("classification:debug")).to be true
    end
  end

  describe "classification:test" do
    it "is defined" do
      expect(Rake::Task.task_defined?("classification:test")).to be true
    end
  end
end
