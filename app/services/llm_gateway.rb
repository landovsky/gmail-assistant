# frozen_string_literal: true

# Client for LLM providers via RubyLLM gem. Makes calls to various LLM providers
# (Gemini, OpenAI, Anthropic) and logs all calls to the LlmCall table for debugging
# and cost monitoring.
class LlmGateway
  class LlmError < StandardError; end
  class RateLimitError < LlmError; end
  class TimeoutError < LlmError; end

  DEFAULT_TIMEOUT = 60

  def initialize(base_url: nil, timeout: nil, user: nil)
    # base_url is deprecated (was used for LiteLLM proxy), kept for backward compatibility
    @timeout = timeout || DEFAULT_TIMEOUT
    @user = user
  end

  # Main entry point: send a chat completion request.
  # Returns { content:, response_text:, tool_calls:, prompt_tokens:, completion_tokens:, total_tokens: }
  def chat(model:, messages:, max_tokens: nil, temperature: 0.7, response_format: nil,
           tools: nil, user: nil, gmail_thread_id: nil, call_type: "classify")
    effective_user = user || @user
    start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)

    # Strip provider prefix if present (backward compatibility)
    normalized_model = normalize_model_name(model)

    # Make the RubyLLM call
    response = make_ruby_llm_call(normalized_model, messages, max_tokens, temperature, response_format, tools)
    parsed = parse_response(response)

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

  def normalize_model_name(model)
    # Strip provider prefix if present (e.g., "gemini/gemini-2.0-flash" -> "gemini-2.0-flash")
    model.to_s.sub(%r{^[^/]+/}, "")
  end

  def make_ruby_llm_call(model, messages, max_tokens, temperature, response_format, tools)
    # Create a new Chat instance
    chat = RubyLLM.chat(model: model)

    # Extract and set system prompt
    system_prompt = extract_system_prompt(messages)
    chat = chat.with_instructions(system_prompt) if system_prompt.present?

    # Set temperature
    chat = chat.with_temperature(temperature) if temperature

    # Set max tokens
    chat = chat.with_max_tokens(max_tokens) if max_tokens

    # Set response format for JSON mode
    if response_format&.dig(:type) == "json_object"
      chat = chat.with_params(response_format: { type: "json_object" })
    end

    # TODO: Handle tools if needed (agent framework feature)
    # For now, raise error if tools are requested
    raise LlmError, "Tool calling not yet supported with RubyLLM" if tools.present?

    # Extract user messages and send them
    user_messages = messages.select { |m| m[:role] == "user" }
    raise LlmError, "No user messages found" if user_messages.empty?

    # Send the user message (combine if multiple)
    combined_user_message = user_messages.map { |m| m[:content] }.join("\n\n")
    response = chat.send_message(combined_user_message)

    response
  rescue RubyLLM::RateLimitError => e
    raise RateLimitError, "Rate limit exceeded: #{e.message}"
  rescue RubyLLM::TimeoutError, Timeout::Error => e
    raise TimeoutError, "LLM timeout: #{e.message}"
  rescue RubyLLM::Error => e
    raise LlmError, "LLM error: #{e.message}"
  rescue StandardError => e
    raise LlmError, "Unexpected error: #{e.message}"
  end

  def parse_response(response)
    # RubyLLM::Message response object
    # Extract content, tool calls, and usage stats
    content = response.content || response.text || ""

    tool_calls = if response.respond_to?(:tool_calls) && response.tool_calls.present?
                   parse_tool_calls(response.tool_calls)
                 end

    # Extract token usage
    usage = response.respond_to?(:usage) ? response.usage : {}
    prompt_tokens = usage[:prompt_tokens] || usage["prompt_tokens"] || 0
    completion_tokens = usage[:completion_tokens] || usage["completion_tokens"] || 0
    total_tokens = usage[:total_tokens] || usage["total_tokens"] || (prompt_tokens + completion_tokens)

    {
      content: content,
      response_text: content,
      tool_calls: tool_calls,
      prompt_tokens: prompt_tokens,
      completion_tokens: completion_tokens,
      total_tokens: total_tokens,
      finish_reason: response.respond_to?(:finish_reason) ? response.finish_reason : "stop"
    }
  end

  def parse_tool_calls(raw_tool_calls)
    return nil if raw_tool_calls.blank?

    raw_tool_calls.map do |tc|
      arguments = tc.respond_to?(:arguments) ? tc.arguments : tc["arguments"]
      parsed_args = arguments.is_a?(String) ? JSON.parse(arguments) : (arguments || {})

      {
        id: tc.respond_to?(:id) ? tc.id : tc["id"],
        name: tc.respond_to?(:name) ? tc.name : tc["name"],
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
