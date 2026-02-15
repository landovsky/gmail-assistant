ENV["BUNDLE_GEMFILE"] ||= File.expand_path("../Gemfile", __dir__)

# This project uses SQLite exclusively. Remove any external DATABASE_URL
# (e.g., from container orchestration) that would override database.yml.
ENV.delete("DATABASE_URL")

require "bundler/setup" # Set up gems listed in the Gemfile.
require "bootsnap/setup" # Speed up boot time by caching expensive operations.
