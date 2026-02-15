# frozen_string_literal: true

require "rails_helper"

RSpec.describe Agent::Preprocessors::CrispPreprocessor do
  let(:preprocessor) { described_class.new }

  describe "#process" do
    it "extracts patient name from From: line" do
      body = "From: Jan Novak\nEmail: jan@example.com\n---\nHello, I need Ibuprofen."
      result = preprocessor.process(subject: "Drug inquiry", body: body, headers: {})

      expect(result[:patient_name]).to eq("Jan Novak")
    end

    it "extracts patient name from Od: line (Czech)" do
      body = "Od: Jana Novakova\n---\nPotrebuji lek."
      result = preprocessor.process(subject: "Dotaz", body: body, headers: {})

      expect(result[:patient_name]).to eq("Jana Novakova")
    end

    it "extracts patient email from Reply-To header" do
      result = preprocessor.process(
        subject: "Test",
        body: "Message body",
        headers: { "Reply-To" => "patient@example.com" }
      )

      expect(result[:patient_email]).to eq("patient@example.com")
    end

    it "extracts patient email from body" do
      body = "From: Jan\nContact: jan.novak@email.cz\n---\nMessage text"
      result = preprocessor.process(subject: "Test", body: body, headers: {})

      expect(result[:patient_email]).to eq("jan.novak@email.cz")
    end

    it "extracts original message after separator" do
      body = "From: Patient\nEmail: test@test.com\n---\nThis is the actual message about drugs."
      result = preprocessor.process(subject: "Inquiry", body: body, headers: {})

      expect(result[:body]).to eq("This is the actual message about drugs.")
    end

    it "builds formatted message with all fields" do
      body = "From: Jan Novak\n---\nI need Ibuprofen 400mg."
      result = preprocessor.process(
        subject: "Drug inquiry",
        body: body,
        headers: { "Reply-To" => "jan@example.com" }
      )

      expect(result[:formatted_message]).to include("Subject: Drug inquiry")
      expect(result[:formatted_message]).to include("Patient name: Jan Novak")
      expect(result[:formatted_message]).to include("Patient email: jan@example.com")
      expect(result[:formatted_message]).to include("I need Ibuprofen 400mg.")
    end

    it "handles emails without forwarding metadata" do
      body = "Plain message without any forwarding headers or separators."
      result = preprocessor.process(subject: "Simple", body: body, headers: {})

      expect(result[:patient_name]).to be_nil
      expect(result[:patient_email]).to be_nil
      expect(result[:body]).to be_present
    end
  end
end
