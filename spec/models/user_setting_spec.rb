# frozen_string_literal: true

require "rails_helper"

RSpec.describe UserSetting do
  describe "validations" do
    subject { build(:user_setting) }

    it { is_expected.to validate_presence_of(:key) }
    it { is_expected.to validate_uniqueness_of(:key).scoped_to(:user_id) }
    it { is_expected.to validate_presence_of(:value) }
  end

  describe "associations" do
    it { is_expected.to belong_to(:user) }
  end

  describe "#parsed_value" do
    it "parses JSON value" do
      setting = build(:user_setting, value: '{"foo": "bar"}')
      expect(setting.parsed_value).to eq({ "foo" => "bar" })
    end

    it "returns raw value for non-JSON" do
      setting = build(:user_setting, value: "plain text")
      expect(setting.parsed_value).to eq("plain text")
    end
  end

  describe "#parsed_value=" do
    it "serializes hash to JSON" do
      setting = build(:user_setting)
      setting.parsed_value = { foo: "bar" }
      expect(setting.value).to eq('{"foo":"bar"}')
    end

    it "keeps strings as-is" do
      setting = build(:user_setting)
      setting.parsed_value = "plain"
      expect(setting.value).to eq("plain")
    end
  end
end
