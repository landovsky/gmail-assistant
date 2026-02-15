# frozen_string_literal: true

# Client for the LiteLLM gateway. Makes HTTP calls to the OpenAI-compatible API
# and logs all calls to the LlmCall table for debugging and cost monitoring.
class LlmGateway
  class LlmError < StandardError; end
  class RateLimitError < LlmError; end
  class TimeoutError < LlmError; end

  DEFAULT_BASE_URL = "http://localhost:4000"
  DEFAULT_TIMEOUT = 60

  def initialize(base_url: nil, timeout: nil, user: nil)
    @base_url = base_url || ENV.fetch("LITELLM_BASE_URL", DEFAULT_BASE_URL)
    @timeout = timeout || DEFAULT_TIMEOUT
    @user = user
  end

  # Main entry point: send a chat completion request.
  # Returns { content:, response_text:, tool_calls:, prompt_tokens:, completion_tokens:, total_tokens: }
  def chat(model:, messages:, max_tokens: nil, temperature: 0.7, response_format: nil,
           tools: nil, user: nil, gmail_thread_id: nil, call_type: "classify")
    effective_user = user || @user
    start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)

    body = build_request_body(model, messages, max_tokens, temperature, response_format, tools)
    raw_response = make_request(body)
    parsed = parse_response(raw_response)

    latency_ms = ((Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time) * 1000).to_i

    # Log to database
    llm_call = LlmCall.log_call(
      call_type: call_type,
      model: model,
      user: effective_user,
      gmail_thread_id: gmail_thread_id,
      system_prompt: extract_system_prompt(messages),
      user_message: extract_user_message(messages),
      response_text: parsed[:response_text] || parsed[:content],
      prompt_tokens: parsed[:prompt_tokens],
      completion_tokens: parsed[:completion_tokens],
      latency_ms: latency_ms
    )

    parsed.merge(llm_call_id: llm_call.id)
  rescue LlmError => e
    latency_ms = ((Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time) * 1000).to_i
    LlmCall.log_call(
      call_type: call_type,
      model: model,
      user: effective_user,
      gmail_thread_id: gmail_thread_id,
      system_prompt: extract_system_prompt(messages),
      user_message: extract_user_message(messages),
      latency_ms: latency_ms,
      error: e.message
    )
    raise
  end

  # Convenience method for structured JSON responses
  def chat_json(model:, messages:, max_tokens: nil, temperature: 0.3, **kwargs)
    result = chat(
      model: model,
      messages: messages,
      max_tokens: max_tokens,
      temperature: temperature,
      response_format: { type: "json_object" },
      **kwargs
    )

    parsed_json = JSON.parse(result[:response_text] || result[:content])
    result.merge(parsed_response: parsed_json)
  rescue JSON::ParserError => e
    raise LlmError, "Failed to parse LLM JSON response: #{e.message}"
  end

  private

  def build_request_body(model, messages, max_tokens, temperature, response_format, tools)
    body = {
      model: model,
      messages: messages,
      temperature: temperature
    }
    body[:max_tokens] = max_tokens if max_tokens
    body[:response_format] = response_format if response_format
    body[:tools] = tools if tools.present?
    body
  end

  def make_request(body)
    response = HTTParty.post(
      "#{@base_url}/v1/chat/completions",
      body: body.to_json,
      headers: request_headers,
      timeout: @timeout
    )

    handle_error_response(response) unless response.success?
    response.parsed_response
  rescue Net::ReadTimeout, Net::OpenTimeout => e
    raise TimeoutError, "LLM gateway timeout: #{e.message}"
  rescue Errno::ECONNREFUSED => e
    raise LlmError, "LLM gateway connection refused: #{e.message}"
  end

  def request_headers
    headers = {
      "Content-Type" => "application/json"
    }
    api_key = ENV.fetch("LITELLM_API_KEY", nil)
    headers["Authorization"] = "Bearer #{api_key}" if api_key.present?
    headers
  end

  def handle_error_response(response)
    case response.code
    when 429
      raise RateLimitError, "Rate limit exceeded: #{response.body}"
    when 400..499
      raise LlmError, "LLM client error (#{response.code}): #{response.body}"
    when 500..599
      raise LlmError, "LLM server error (#{response.code}): #{response.body}"
    else
      raise LlmError, "Unexpected LLM response (#{response.code}): #{response.body}"
    end
  end

  def parse_response(raw)
    choice = raw.dig("choices", 0)
    raise LlmError, "No choices in LLM response" unless choice

    message = choice["message"] || {}
    tool_calls = parse_tool_calls(message["tool_calls"])

    {
      content: message["content"],
      response_text: message["content"] || "",
      tool_calls: tool_calls,
      prompt_tokens: raw.dig("usage", "prompt_tokens") || 0,
      completion_tokens: raw.dig("usage", "completion_tokens") || 0,
      total_tokens: raw.dig("usage", "total_tokens") || 0,
      finish_reason: choice["finish_reason"]
    }
  end

  def parse_tool_calls(raw_tool_calls)
    return nil if raw_tool_calls.blank?

    raw_tool_calls.map do |tc|
      arguments = tc.dig("function", "arguments")
      parsed_args = arguments.is_a?(String) ? JSON.parse(arguments) : (arguments || {})

      {
        id: tc["id"],
        name: tc.dig("function", "name"),
        arguments: parsed_args
      }
    end
  rescue JSON::ParserError
    nil
  end

  def extract_system_prompt(messages)
    messages.find { |m| m[:role] == "system" }&.dig(:content)
  end

  def extract_user_message(messages)
    messages.select { |m| m[:role] == "user" }.last&.dig(:content)
  end
end
