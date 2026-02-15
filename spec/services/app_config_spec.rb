# frozen_string_literal: true

require "rails_helper"

RSpec.describe AppConfig do
  before { described_class.reload! }

  after { described_class.reload! }

  describe ".get" do
    it "reads values from the YAML config" do
      expect(described_class.get(:llm, :classify_model)).to eq("gemini/gemini-2.0-flash")
    end

    it "returns default when section is missing" do
      expect(described_class.get(:nonexistent, :key, default: "fallback")).to eq("fallback")
    end

    it "returns default when key is missing" do
      expect(described_class.get(:llm, :nonexistent, default: "fallback")).to eq("fallback")
    end

    context "with environment variable override" do
      around do |example|
        ENV["GMA_LLM_CLASSIFY_MODEL"] = "override-model"
        described_class.reload!
        example.run
        ENV.delete("GMA_LLM_CLASSIFY_MODEL")
      end

      it "prefers environment variable over YAML" do
        expect(described_class.get(:llm, :classify_model)).to eq("override-model")
      end
    end
  end

  describe ".llm" do
    it "returns LLM configuration" do
      config = described_class.llm
      expect(config.classify_model).to eq("gemini/gemini-2.0-flash")
      expect(config.draft_model).to eq("gemini/gemini-2.5-pro")
      expect(config.max_classify_tokens).to eq(256)
      expect(config.max_draft_tokens).to eq(2048)
    end
  end

  describe ".sync" do
    it "returns sync configuration" do
      config = described_class.sync
      expect(config.fallback_interval_minutes).to eq(15)
      expect(config.full_sync_interval_hours).to eq(1)
      expect(config.history_max_results).to eq(100)
    end
  end

  describe ".auth" do
    it "returns auth configuration" do
      config = described_class.auth
      expect(config.mode).to eq("personal_oauth")
      expect(config.credentials_file).to eq("config/credentials.json")
    end
  end
end
