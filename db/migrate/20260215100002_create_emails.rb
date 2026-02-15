# frozen_string_literal: true

class CreateEmails < ActiveRecord::Migration[8.1]
  def change
    create_table :emails do |t|
      t.references :user, null: false, foreign_key: true
      t.string :gmail_thread_id, null: false
      t.string :gmail_message_id, null: false
      t.string :sender_email, null: false
      t.string :sender_name
      t.string :subject
      t.text :snippet
      t.datetime :received_at
      t.string :classification, null: false, default: "pending"
      t.string :confidence, null: false, default: "medium"
      t.text :reasoning
      t.string :detected_language, null: false, default: "cs"
      t.string :resolved_style, null: false, default: "business"
      t.integer :message_count, null: false, default: 1
      t.string :status, null: false, default: "pending"
      t.string :draft_id
      t.integer :rework_count, null: false, default: 0
      t.text :last_rework_instruction
      t.string :vendor_name
      t.datetime :processed_at
      t.datetime :drafted_at
      t.datetime :acted_at

      t.timestamps
    end

    add_index :emails, %i[user_id gmail_thread_id], unique: true
    add_index :emails, %i[user_id classification]
    add_index :emails, %i[user_id status]
    add_index :emails, :gmail_thread_id
  end
end
