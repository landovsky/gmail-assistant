# frozen_string_literal: true

class CreateLlmCalls < ActiveRecord::Migration[8.1]
  def change
    create_table :llm_calls do |t|
      t.references :user, foreign_key: true, index: false
      t.string :gmail_thread_id
      t.string :call_type, null: false
      t.string :model, null: false
      t.text :system_prompt
      t.text :user_message
      t.text :response_text
      t.integer :prompt_tokens, null: false, default: 0
      t.integer :completion_tokens, null: false, default: 0
      t.integer :total_tokens, null: false, default: 0
      t.integer :latency_ms, null: false, default: 0
      t.text :error

      t.datetime :created_at, null: false
    end

    add_index :llm_calls, :gmail_thread_id
    add_index :llm_calls, :call_type
    add_index :llm_calls, :user_id
    add_index :llm_calls, :created_at
  end
end
