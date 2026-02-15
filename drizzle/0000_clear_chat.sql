CREATE TABLE `agent_runs` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`user_id` integer NOT NULL,
	`gmail_thread_id` text NOT NULL,
	`profile` text NOT NULL,
	`status` text DEFAULT 'running' NOT NULL,
	`tool_calls_log` text DEFAULT '[]' NOT NULL,
	`final_message` text,
	`iterations` integer DEFAULT 0 NOT NULL,
	`error` text,
	`created_at` text DEFAULT (datetime('now')) NOT NULL,
	`completed_at` text,
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `agent_runs_user_id_idx` ON `agent_runs` (`user_id`);--> statement-breakpoint
CREATE INDEX `agent_runs_gmail_thread_idx` ON `agent_runs` (`gmail_thread_id`);--> statement-breakpoint
CREATE INDEX `agent_runs_status_idx` ON `agent_runs` (`status`);--> statement-breakpoint
CREATE TABLE `email_events` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`user_id` integer NOT NULL,
	`gmail_thread_id` text NOT NULL,
	`event_type` text NOT NULL,
	`detail` text,
	`label_id` text,
	`draft_id` text,
	`created_at` text DEFAULT (datetime('now')) NOT NULL,
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `email_events_user_thread_idx` ON `email_events` (`user_id`,`gmail_thread_id`);--> statement-breakpoint
CREATE INDEX `email_events_event_type_idx` ON `email_events` (`event_type`);--> statement-breakpoint
CREATE TABLE `emails` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`user_id` integer NOT NULL,
	`gmail_thread_id` text NOT NULL,
	`gmail_message_id` text NOT NULL,
	`sender_email` text NOT NULL,
	`sender_name` text,
	`subject` text,
	`snippet` text,
	`received_at` text,
	`classification` text NOT NULL,
	`confidence` text DEFAULT 'medium' NOT NULL,
	`reasoning` text,
	`detected_language` text DEFAULT 'cs' NOT NULL,
	`resolved_style` text DEFAULT 'business' NOT NULL,
	`message_count` integer DEFAULT 1 NOT NULL,
	`status` text DEFAULT 'pending' NOT NULL,
	`draft_id` text,
	`rework_count` integer DEFAULT 0 NOT NULL,
	`last_rework_instruction` text,
	`vendor_name` text,
	`processed_at` text DEFAULT (datetime('now')) NOT NULL,
	`drafted_at` text,
	`acted_at` text,
	`created_at` text DEFAULT (datetime('now')) NOT NULL,
	`updated_at` text DEFAULT (datetime('now')) NOT NULL,
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `emails_user_thread_idx` ON `emails` (`user_id`,`gmail_thread_id`);--> statement-breakpoint
CREATE INDEX `emails_user_classification_idx` ON `emails` (`user_id`,`classification`);--> statement-breakpoint
CREATE INDEX `emails_user_status_idx` ON `emails` (`user_id`,`status`);--> statement-breakpoint
CREATE INDEX `emails_gmail_thread_idx` ON `emails` (`gmail_thread_id`);--> statement-breakpoint
CREATE TABLE `jobs` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`job_type` text NOT NULL,
	`user_id` integer NOT NULL,
	`payload` text DEFAULT '{}' NOT NULL,
	`status` text DEFAULT 'pending' NOT NULL,
	`attempts` integer DEFAULT 0 NOT NULL,
	`max_attempts` integer DEFAULT 3 NOT NULL,
	`error_message` text,
	`created_at` text DEFAULT (datetime('now')) NOT NULL,
	`started_at` text,
	`completed_at` text,
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `jobs_status_created_idx` ON `jobs` (`status`,`created_at`);--> statement-breakpoint
CREATE INDEX `jobs_user_job_type_idx` ON `jobs` (`user_id`,`job_type`);--> statement-breakpoint
CREATE TABLE `llm_calls` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`user_id` integer,
	`gmail_thread_id` text,
	`call_type` text NOT NULL,
	`model` text NOT NULL,
	`system_prompt` text,
	`user_message` text,
	`response_text` text,
	`prompt_tokens` integer DEFAULT 0 NOT NULL,
	`completion_tokens` integer DEFAULT 0 NOT NULL,
	`total_tokens` integer DEFAULT 0 NOT NULL,
	`latency_ms` integer DEFAULT 0 NOT NULL,
	`error` text,
	`created_at` text DEFAULT (datetime('now')) NOT NULL,
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `llm_calls_gmail_thread_idx` ON `llm_calls` (`gmail_thread_id`);--> statement-breakpoint
CREATE INDEX `llm_calls_call_type_idx` ON `llm_calls` (`call_type`);--> statement-breakpoint
CREATE INDEX `llm_calls_user_id_idx` ON `llm_calls` (`user_id`);--> statement-breakpoint
CREATE INDEX `llm_calls_created_at_idx` ON `llm_calls` (`created_at`);--> statement-breakpoint
CREATE TABLE `sync_state` (
	`user_id` integer PRIMARY KEY NOT NULL,
	`last_history_id` text DEFAULT '0' NOT NULL,
	`last_sync_at` text DEFAULT (datetime('now')) NOT NULL,
	`watch_expiration` text,
	`watch_resource_id` text,
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `user_labels` (
	`user_id` integer NOT NULL,
	`label_key` text NOT NULL,
	`gmail_label_id` text NOT NULL,
	`gmail_label_name` text NOT NULL,
	PRIMARY KEY(`user_id`, `label_key`),
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `user_settings` (
	`user_id` integer NOT NULL,
	`setting_key` text NOT NULL,
	`setting_value` text NOT NULL,
	PRIMARY KEY(`user_id`, `setting_key`),
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `users` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`email` text NOT NULL,
	`display_name` text,
	`is_active` integer DEFAULT true NOT NULL,
	`onboarded_at` text,
	`created_at` text DEFAULT (datetime('now')) NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `users_email_unique` ON `users` (`email`);