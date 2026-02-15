# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Api::Reset", type: :request do
  describe "POST /api/reset" do
    it "deletes transient data and preserves users/labels/settings" do
      user = create(:user)
      create(:user_label, user: user, label_key: "fyi", gmail_label_id: "Label_1")
      create(:user_setting, user: user, key: "lang", value: '"en"')
      create(:email, user: user)
      create(:job, user: user)
      user.sync_state.update!(last_history_id: "500")

      post "/api/reset"

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["deleted"]["emails"]).to eq(1)
      expect(body["deleted"]["jobs"]).to eq(1)
      expect(body["total"]).to be > 0

      # User, labels, settings preserved
      expect(User.count).to eq(1)
      expect(UserLabel.count).to eq(1)
      expect(UserSetting.count).to eq(1)

      # Transient data cleared
      expect(Email.count).to eq(0)
      expect(Job.count).to eq(0)

      # Sync state reset
      expect(user.sync_state.reload.last_history_id).to eq("0")
    end
  end
end
