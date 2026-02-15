# frozen_string_literal: true

# Client for LLM providers via RubyLLM gem. Makes calls to various LLM providers
# (Gemini, OpenAI, Anthropic) and logs all calls to the LlmCall table for debugging
# and cost monitoring.
class LlmGateway
  class LlmError < StandardError; end
  class RateLimitError < LlmError; end
  class TimeoutError < LlmError; end

  DEFAULT_TIMEOUT = 60

  def initialize(timeout: nil, user: nil, **_deprecated)
    @timeout = timeout || DEFAULT_TIMEOUT
    @user = user
  end

  # Main entry point: send a chat completion request.
  # Returns { content:, response_text:, tool_calls:, prompt_tokens:, completion_tokens:, total_tokens: }
  def chat(model:, messages:, max_tokens: nil, temperature: 0.7, response_format: nil,
           tools: nil, user: nil, gmail_thread_id: nil, call_type: 'classify')
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
  def chat_json(model:, messages:, max_tokens: nil, temperature: 0.3, **)
    result = chat(
      model: model,
      messages: messages,
      max_tokens: max_tokens,
      temperature: temperature,
      response_format: { type: 'json_object' },
      **
    )

    parsed_json = JSON.parse(result[:response_text] || result[:content])
    result.merge(parsed_response: parsed_json)
  rescue JSON::ParserError => e
    raise LlmError, "Failed to parse LLM JSON response: #{e.message}"
  end

  private

  def normalize_model_name(model)
    # Strip provider prefix if present (e.g., "gemini/gemini-2.0-flash" -> "gemini-2.0-flash")
    model.to_s.sub(%r{^[^/]+/}, '')
  end

  def make_ruby_llm_call(model, messages, max_tokens, temperature, response_format, tools) # rubocop:disable Metrics/ParameterLists
    chat = RubyLLM.chat(model: model)

    system_prompt = extract_system_prompt(messages)
    chat = chat.with_instructions(system_prompt) if system_prompt.present?
    chat = chat.with_temperature(temperature) if temperature

    # JSON mode: use RubyLLM's with_schema which handles provider differences
    # (Gemini uses responseMimeType, OpenAI uses response_format)
    chat = chat.with_schema({ type: 'object' }) if response_format&.dig(:type) == 'json_object'

    # Max tokens: translate to provider-native params via with_params
    chat = chat.with_params(provider_max_tokens_params(model, max_tokens)) if max_tokens

    Rails.logger.warn('LlmGateway: tool calling not yet supported with RubyLLM, ignoring tools') if tools.present?

    user_messages = messages.select { |m| m[:role] == 'user' }
    raise LlmError, 'No user messages found' if user_messages.empty?

    combined_user_message = user_messages.map { |m| m[:content] }.join("\n\n")
    chat.ask(combined_user_message)
  rescue RubyLLM::RateLimitError => e
    raise RateLimitError, "Rate limit exceeded: #{e.message}"
  rescue Timeout::Error, Faraday::TimeoutError, Faraday::ConnectionFailed => e
    raise TimeoutError, "LLM timeout: #{e.message}"
  rescue RubyLLM::Error => e
    raise LlmError, "LLM error: #{e.message}"
  end

  def parse_response(response)
    # RubyLLM auto-parses JSON into a Hash when with_schema is used;
    # convert back to JSON string for consistent return type
    raw_content = response.content
    content = raw_content.is_a?(Hash) ? raw_content.to_json : raw_content.to_s

    tool_calls = if response.respond_to?(:tool_calls) && response.tool_calls.present?
                   parse_tool_calls(response.tool_calls)
                 end

    prompt_tokens = response.input_tokens || 0
    completion_tokens = response.output_tokens || 0

    {
      content: content,
      response_text: content,
      tool_calls: tool_calls,
      prompt_tokens: prompt_tokens,
      completion_tokens: completion_tokens,
      total_tokens: prompt_tokens + completion_tokens,
      finish_reason: 'stop'
    }
  end

  def parse_tool_calls(raw_tool_calls)
    return nil if raw_tool_calls.blank?

    raw_tool_calls.map do |tc|
      arguments = tc.respond_to?(:arguments) ? tc.arguments : tc['arguments']
      parsed_args = arguments.is_a?(String) ? JSON.parse(arguments) : (arguments || {})

      {
        id: tc.respond_to?(:id) ? tc.id : tc['id'],
        name: tc.respond_to?(:name) ? tc.name : tc['name'],
        arguments: parsed_args
      }
    end
  rescue JSON::ParserError
    nil
  end

  # Translate max_tokens to provider-native payload structure.
  # RubyLLM's with_params deep-merges into the raw API payload,
  # so we must use each provider's native field names.
  def provider_max_tokens_params(model, max_tokens)
    if model.to_s.match?(/gemini/i)
      { generationConfig: { maxOutputTokens: max_tokens } }
    elsif model.to_s.match?(/claude/i)
      { max_tokens: max_tokens }
    else
      # OpenAI and compatible APIs
      { max_completion_tokens: max_tokens }
    end
  end

  def extract_system_prompt(messages)
    messages.find { |m| m[:role] == 'system' }&.dig(:content)
  end

  def extract_user_message(messages)
    messages.select { |m| m[:role] == 'user' }.last&.dig(:content)
  end
end
