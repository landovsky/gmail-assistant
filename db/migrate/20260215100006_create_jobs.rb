# frozen_string_literal: true

class CreateJobs < ActiveRecord::Migration[8.1]
  def change
    create_table :jobs do |t|
      t.string :job_type, null: false
      t.references :user, null: false, foreign_key: true
      t.text :payload, null: false, default: "{}"
      t.string :status, null: false, default: "pending"
      t.integer :attempts, null: false, default: 0
      t.integer :max_attempts, null: false, default: 3
      t.text :error_message
      t.datetime :started_at
      t.datetime :completed_at

      t.timestamps
    end

    add_index :jobs, %i[status created_at]
    add_index :jobs, %i[user_id job_type]
  end
end
