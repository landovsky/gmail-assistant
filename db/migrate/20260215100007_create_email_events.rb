# frozen_string_literal: true

class CreateEmailEvents < ActiveRecord::Migration[8.1]
  def change
    create_table :email_events do |t|
      t.references :user, null: false, foreign_key: true
      t.string :gmail_thread_id, null: false
      t.string :event_type, null: false
      t.text :detail
      t.string :label_id
      t.string :draft_id

      t.datetime :created_at, null: false
    end

    add_index :email_events, %i[user_id gmail_thread_id]
    add_index :email_events, :event_type
  end
end
