# This file is auto-generated from the current state of the database. Instead
# of editing this file, please use the migrations feature of Active Record to
# incrementally modify your database, and then regenerate this schema definition.
#
# This file is the source Rails uses to define your schema when running `bin/rails
# db:schema:load`. When creating a new database, `bin/rails db:schema:load` tends to
# be faster and is potentially less error prone than running all of your
# migrations from scratch. Old migrations may fail to apply correctly if those
# migrations use external dependencies or application code.
#
# It's strongly recommended that you check this file into your version control system.

ActiveRecord::Schema[8.1].define(version: 2026_02_15_100009) do
  create_table "agent_runs", force: :cascade do |t|
    t.datetime "completed_at"
    t.datetime "created_at", null: false
    t.text "error"
    t.text "final_message"
    t.string "gmail_thread_id", null: false
    t.integer "iterations", default: 0, null: false
    t.string "profile", null: false
    t.string "status", default: "running", null: false
    t.text "tool_calls_log", default: "[]", null: false
    t.integer "user_id", null: false
    t.index ["gmail_thread_id"], name: "index_agent_runs_on_gmail_thread_id"
    t.index ["status"], name: "index_agent_runs_on_status"
    t.index ["user_id"], name: "index_agent_runs_on_user_id"
  end

  create_table "email_events", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.text "detail"
    t.string "draft_id"
    t.string "event_type", null: false
    t.string "gmail_thread_id", null: false
    t.string "label_id"
    t.integer "user_id", null: false
    t.index ["event_type"], name: "index_email_events_on_event_type"
    t.index ["user_id", "gmail_thread_id"], name: "index_email_events_on_user_id_and_gmail_thread_id"
    t.index ["user_id"], name: "index_email_events_on_user_id"
  end

  create_table "emails", force: :cascade do |t|
    t.datetime "acted_at"
    t.string "classification", default: "pending", null: false
    t.string "confidence", default: "medium", null: false
    t.datetime "created_at", null: false
    t.string "detected_language", default: "cs", null: false
    t.string "draft_id"
    t.datetime "drafted_at"
    t.string "gmail_message_id", null: false
    t.string "gmail_thread_id", null: false
    t.text "last_rework_instruction"
    t.integer "message_count", default: 1, null: false
    t.datetime "processed_at"
    t.text "reasoning"
    t.datetime "received_at"
    t.string "resolved_style", default: "business", null: false
    t.integer "rework_count", default: 0, null: false
    t.string "sender_email", null: false
    t.string "sender_name"
    t.text "snippet"
    t.string "status", default: "pending", null: false
    t.string "subject"
    t.datetime "updated_at", null: false
    t.integer "user_id", null: false
    t.string "vendor_name"
    t.index ["gmail_thread_id"], name: "index_emails_on_gmail_thread_id"
    t.index ["user_id", "classification"], name: "index_emails_on_user_id_and_classification"
    t.index ["user_id", "gmail_thread_id"], name: "index_emails_on_user_id_and_gmail_thread_id", unique: true
    t.index ["user_id", "status"], name: "index_emails_on_user_id_and_status"
    t.index ["user_id"], name: "index_emails_on_user_id"
  end

  create_table "jobs", force: :cascade do |t|
    t.integer "attempts", default: 0, null: false
    t.datetime "completed_at"
    t.datetime "created_at", null: false
    t.text "error_message"
    t.string "job_type", null: false
    t.integer "max_attempts", default: 3, null: false
    t.text "payload", default: "{}", null: false
    t.datetime "started_at"
    t.string "status", default: "pending", null: false
    t.datetime "updated_at", null: false
    t.integer "user_id", null: false
    t.index ["status", "created_at"], name: "index_jobs_on_status_and_created_at"
    t.index ["user_id", "job_type"], name: "index_jobs_on_user_id_and_job_type"
    t.index ["user_id"], name: "index_jobs_on_user_id"
  end

  create_table "llm_calls", force: :cascade do |t|
    t.string "call_type", null: false
    t.integer "completion_tokens", default: 0, null: false
    t.datetime "created_at", null: false
    t.text "error"
    t.string "gmail_thread_id"
    t.integer "latency_ms", default: 0, null: false
    t.string "model", null: false
    t.integer "prompt_tokens", default: 0, null: false
    t.text "response_text"
    t.text "system_prompt"
    t.integer "total_tokens", default: 0, null: false
    t.integer "user_id"
    t.text "user_message"
    t.index ["call_type"], name: "index_llm_calls_on_call_type"
    t.index ["created_at"], name: "index_llm_calls_on_created_at"
    t.index ["gmail_thread_id"], name: "index_llm_calls_on_gmail_thread_id"
    t.index ["user_id"], name: "index_llm_calls_on_user_id"
  end

  create_table "sync_states", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.string "last_history_id", default: "0", null: false
    t.datetime "last_sync_at"
    t.datetime "updated_at", null: false
    t.integer "user_id", null: false
    t.datetime "watch_expiration"
    t.string "watch_resource_id"
    t.index ["user_id"], name: "index_sync_states_on_user_id", unique: true
  end

  create_table "user_labels", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.string "gmail_label_id", null: false
    t.string "gmail_label_name", null: false
    t.string "label_key", null: false
    t.datetime "updated_at", null: false
    t.integer "user_id", null: false
    t.index ["user_id", "label_key"], name: "index_user_labels_on_user_id_and_label_key", unique: true
    t.index ["user_id"], name: "index_user_labels_on_user_id"
  end

  create_table "user_settings", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.string "key", null: false
    t.datetime "updated_at", null: false
    t.integer "user_id", null: false
    t.text "value", null: false
    t.index ["user_id", "key"], name: "index_user_settings_on_user_id_and_key", unique: true
    t.index ["user_id"], name: "index_user_settings_on_user_id"
  end

  create_table "users", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.string "display_name"
    t.string "email", null: false
    t.boolean "is_active", default: true, null: false
    t.datetime "onboarded_at"
    t.datetime "updated_at", null: false
    t.index ["email"], name: "index_users_on_email", unique: true
  end

  add_foreign_key "agent_runs", "users"
  add_foreign_key "email_events", "users"
  add_foreign_key "emails", "users"
  add_foreign_key "jobs", "users"
  add_foreign_key "llm_calls", "users"
  add_foreign_key "sync_states", "users"
  add_foreign_key "user_labels", "users"
  add_foreign_key "user_settings", "users"
end
