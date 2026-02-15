# frozen_string_literal: true

require "rails_helper"

RSpec.describe AgentRun do
  describe "validations" do
    it { is_expected.to validate_presence_of(:gmail_thread_id) }
    it { is_expected.to validate_presence_of(:profile) }
    it { is_expected.to validate_inclusion_of(:status).in_array(described_class::STATUSES) }
    it { is_expected.to validate_numericality_of(:iterations).is_greater_than_or_equal_to(0) }
  end

  describe "associations" do
    it { is_expected.to belong_to(:user) }
  end

  describe "#log_tool_call" do
    it "appends tool call and increments iterations" do
      run = create(:agent_run)
      run.log_tool_call(tool_name: "search", input: "query", output: "results")

      calls = run.parsed_tool_calls
      expect(calls.length).to eq(1)
      expect(calls.first["tool"]).to eq("search")
      expect(run.iterations).to eq(1)
    end
  end

  describe "#complete!" do
    it "marks run as completed" do
      run = create(:agent_run)
      run.complete!("Done")

      expect(run.status).to eq("completed")
      expect(run.final_message).to eq("Done")
      expect(run.completed_at).to be_present
    end
  end

  describe "#fail!" do
    it "marks run as error" do
      run = create(:agent_run)
      run.fail!("Something broke")

      expect(run.status).to eq("error")
      expect(run.error).to eq("Something broke")
    end
  end

  describe "#max_iterations!" do
    it "marks run as max_iterations" do
      run = create(:agent_run, iterations: 10)
      run.max_iterations!("Reached limit")

      expect(run.status).to eq("max_iterations")
      expect(run.final_message).to eq("Reached limit")
    end
  end
end
