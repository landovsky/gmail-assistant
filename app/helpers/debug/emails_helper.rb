# frozen_string_literal: true

module Debug
  module EmailsHelper
    def sort_link(label, column, filters)
      direction = if filters[:sort] == column && filters[:direction] == "asc"
                    "desc"
                  else
                    "asc"
                  end

      arrow = if filters[:sort] == column
                filters[:direction] == "asc" ? " ▲" : " ▼"
              else
                ""
              end

      query_params = filters.except(:sort, :direction).compact
      query_params[:sort] = column
      query_params[:direction] = direction

      link_to "#{label}#{arrow}".html_safe, "/debug/emails?#{query_params.to_query}"
    end

    def pagination_link(label, page, filters, current = false)
      query_params = filters.compact
      query_params[:page] = page

      if current
        "<span class=\"btn btn-sm\" style=\"background: var(--purple); color: white;\">#{label}</span>".html_safe
      else
        link_to label.html_safe, "/debug/emails?#{query_params.to_query}", class: "btn btn-sm"
      end
    end
  end
end
