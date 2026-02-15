# frozen_string_literal: true

class CreateUserSettings < ActiveRecord::Migration[8.1]
  def change
    create_table :user_settings do |t|
      t.references :user, null: false, foreign_key: true
      t.string :key, null: false
      t.text :value, null: false

      t.timestamps
    end

    add_index :user_settings, %i[user_id key], unique: true
  end
end
