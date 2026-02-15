# frozen_string_literal: true

module Api
  class BriefingController < BaseController
    # GET /api/briefing/:user_email
    # Get inbox briefing/summary for a user.
    def show
      user = User.find_by!(email: params[:user_email])
      summary = build_summary(user)

      pending_drafts = user.emails.where(classification: "needs_response", status: "pending").count
      active_needs_response = user.emails.where(classification: "needs_response")
                                         .where.not(status: %w[sent archived]).count
      active_action_required = user.emails.where(classification: "action_required")
                                          .where.not(status: %w[sent archived]).count

      render json: {
        user: user.email,
        summary: summary,
        pending_drafts: pending_drafts,
        action_items: active_needs_response + active_action_required
      }
    end

    private

    def build_summary(user)
      Email::CLASSIFICATIONS.each_with_object({}) do |classification, result|
        emails = user.emails.by_classification(classification)
        active = emails.where.not(status: %w[sent archived])
        items = active.recent.limit(10).map do |email|
          {
            thread_id: email.gmail_thread_id,
            subject: email.subject,
            sender: email.sender_email,
            status: email.status,
            confidence: email.confidence
          }
        end

        result[classification] = {
          total: emails.count,
          active: active.count,
          items: items
        }
      end
    end
  end
end
