# frozen_string_literal: true

class CreateUsers < ActiveRecord::Migration[8.1]
  def change
    create_table :users do |t|
      t.string :email, null: false
      t.string :display_name
      t.boolean :is_active, null: false, default: true
      t.datetime :onboarded_at

      t.timestamps
    end

    add_index :users, :email, unique: true
  end
end
