# frozen_string_literal: true

class CreateAgentRuns < ActiveRecord::Migration[8.1]
  def change
    create_table :agent_runs do |t|
      t.references :user, null: false, foreign_key: true, index: false
      t.string :gmail_thread_id, null: false
      t.string :profile, null: false
      t.string :status, null: false, default: "running"
      t.text :tool_calls_log, null: false, default: "[]"
      t.text :final_message
      t.integer :iterations, null: false, default: 0
      t.text :error
      t.datetime :completed_at

      t.datetime :created_at, null: false
    end

    add_index :agent_runs, :user_id
    add_index :agent_runs, :gmail_thread_id
    add_index :agent_runs, :status
  end
end
