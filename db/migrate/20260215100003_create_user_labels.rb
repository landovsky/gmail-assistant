# frozen_string_literal: true

class CreateUserLabels < ActiveRecord::Migration[8.1]
  def change
    create_table :user_labels do |t|
      t.references :user, null: false, foreign_key: true
      t.string :label_key, null: false
      t.string :gmail_label_id, null: false
      t.string :gmail_label_name, null: false

      t.timestamps
    end

    add_index :user_labels, %i[user_id label_key], unique: true
  end
end
