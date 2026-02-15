# frozen_string_literal: true

class CreateSyncStates < ActiveRecord::Migration[8.1]
  def change
    create_table :sync_states do |t|
      t.references :user, null: false, foreign_key: true, index: { unique: true }
      t.string :last_history_id, null: false, default: "0"
      t.datetime :last_sync_at
      t.datetime :watch_expiration
      t.string :watch_resource_id

      t.timestamps
    end
  end
end
