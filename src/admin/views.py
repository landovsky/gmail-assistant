"""Admin views — SQLAdmin ModelView classes for each table."""

from __future__ import annotations

from sqladmin import ModelView

from src.admin.models import (
    EmailEventModel,
    EmailModel,
    JobModel,
    LLMCallModel,
    SyncStateModel,
    UserLabelModel,
    UserModel,
    UserSettingModel,
)


class UserAdmin(ModelView, model=UserModel):
    """User admin view."""

    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"

    # Read-only
    can_create = False
    can_edit = False
    can_delete = False

    # List view columns
    column_list = ["id", "email", "display_name", "is_active", "onboarded_at", "created_at"]
    column_searchable_list = ["email", "display_name"]
    column_sortable_list = ["id", "email", "created_at"]
    column_default_sort = ("id", True)

    # Detail view
    column_details_list = [
        "id",
        "email",
        "display_name",
        "is_active",
        "onboarded_at",
        "created_at",
    ]


class UserLabelAdmin(ModelView, model=UserLabelModel):
    """User label admin view."""

    name = "User Label"
    name_plural = "User Labels"
    icon = "fa-solid fa-tag"

    can_create = False
    can_edit = False
    can_delete = False

    column_list = ["id", "user_id", "label_key", "gmail_label_id", "gmail_label_name"]
    column_searchable_list = ["label_key", "gmail_label_name"]
    column_sortable_list = ["user_id", "label_key"]


class UserSettingAdmin(ModelView, model=UserSettingModel):
    """User setting admin view."""

    name = "User Setting"
    name_plural = "User Settings"
    icon = "fa-solid fa-cog"

    can_create = False
    can_edit = False
    can_delete = False

    column_list = ["id", "user_id", "setting_key", "created_at"]
    column_searchable_list = ["setting_key"]
    column_sortable_list = ["user_id", "setting_key"]


class SyncStateAdmin(ModelView, model=SyncStateModel):
    """Sync state admin view."""

    name = "Sync State"
    name_plural = "Sync States"
    icon = "fa-solid fa-sync"

    can_create = False
    can_edit = False
    can_delete = False

    column_list = [
        "id",
        "user_id",
        "last_history_id",
        "last_sync_at",
        "watch_expiration",
    ]
    column_sortable_list = ["user_id", "last_sync_at"]


class EmailAdmin(ModelView, model=EmailModel):
    """Email admin view — primary debugging interface."""

    name = "Email"
    name_plural = "Emails"
    icon = "fa-solid fa-envelope"

    can_create = False
    can_edit = False
    can_delete = False

    # List view — show key classification and status fields
    column_list = [
        "id",
        "user_id",
        "subject",
        "sender_email",
        "classification",
        "resolved_style",
        "status",
        "confidence",
        "received_at",
    ]
    column_searchable_list = ["subject", "sender_email", "gmail_thread_id"]
    column_sortable_list = [
        "id",
        "user_id",
        "classification",
        "status",
        "received_at",
    ]
    column_default_sort = ("id", True)

    # Detail view — show everything including related events/LLM calls
    column_details_list = [
        "id",
        "user_id",
        "gmail_thread_id",
        "gmail_message_id",
        "sender_email",
        "sender_name",
        "subject",
        "snippet",
        "received_at",
        "classification",
        "confidence",
        "reasoning",
        "detected_language",
        "resolved_style",
        "message_count",
        "status",
        "draft_id",
        "rework_count",
        "last_rework_instruction",
        "vendor_name",
        "processed_at",
        "drafted_at",
        "acted_at",
        "created_at",
        "updated_at",
    ]


class EmailEventAdmin(ModelView, model=EmailEventModel):
    """Email event admin view — audit trail."""

    name = "Email Event"
    name_plural = "Email Events"
    icon = "fa-solid fa-history"

    can_create = False
    can_edit = False
    can_delete = False

    column_list = [
        "id",
        "user_id",
        "gmail_thread_id",
        "event_type",
        "detail",
        "created_at",
    ]
    column_searchable_list = ["gmail_thread_id", "event_type", "detail"]
    column_sortable_list = ["id", "user_id", "event_type", "created_at"]
    column_default_sort = ("created_at", True)


class LLMCallAdmin(ModelView, model=LLMCallModel):
    """LLM call admin view — debugging LLM decisions."""

    name = "LLM Call"
    name_plural = "LLM Calls"
    icon = "fa-solid fa-brain"

    can_create = False
    can_edit = False
    can_delete = False

    # List view — show type, model, tokens, latency
    column_list = [
        "id",
        "user_id",
        "gmail_thread_id",
        "call_type",
        "model",
        "total_tokens",
        "latency_ms",
        "error",
        "created_at",
    ]
    column_searchable_list = ["gmail_thread_id", "call_type", "model"]
    column_sortable_list = [
        "id",
        "user_id",
        "call_type",
        "total_tokens",
        "latency_ms",
        "created_at",
    ]
    column_default_sort = ("created_at", True)

    # Detail view — show full prompts and response
    column_details_list = [
        "id",
        "user_id",
        "gmail_thread_id",
        "call_type",
        "model",
        "system_prompt",
        "user_message",
        "response_text",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "latency_ms",
        "error",
        "created_at",
    ]


class JobAdmin(ModelView, model=JobModel):
    """Job admin view — background job queue."""

    name = "Job"
    name_plural = "Jobs"
    icon = "fa-solid fa-tasks"

    can_create = False
    can_edit = False
    can_delete = False

    column_list = [
        "id",
        "user_id",
        "job_type",
        "status",
        "attempts",
        "error_message",
        "created_at",
    ]
    column_searchable_list = ["job_type", "status"]
    column_sortable_list = ["id", "user_id", "job_type", "status", "created_at"]
    column_default_sort = ("created_at", True)
