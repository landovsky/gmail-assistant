# frozen_string_literal: true

module Agent
  # Core agent loop implementing the tool-use pattern.
  # Sends messages to LLM, executes tool calls, and iterates until completion.
  class Loop
    DEFAULT_MAX_ITERATIONS = 10

    def initialize(user:, gmail_client: nil)
      @user = user
      @gmail_client = gmail_client || Gmail::Client.new(user: user)
      @llm = LlmGateway.new(user: user)
    end

    # Execute the agent loop for a given thread.
    # Returns the AgentRun record.
    def execute(gmail_thread_id:, profile_name:, user_message:)
      profile = load_profile(profile_name)
      tool_schemas = Agent::ToolRegistry.instance.tools_for_profile(profile[:tools])

      # Create agent run record
      agent_run = AgentRun.create!(
        user: @user,
        gmail_thread_id: gmail_thread_id,
        profile: profile_name,
        status: "running"
      )

      # Build conversation
      messages = [
        { role: "system", content: profile[:system_prompt] },
        { role: "user", content: user_message }
      ]

      max_iterations = profile[:max_iterations] || DEFAULT_MAX_ITERATIONS
      iteration = 0

      begin
        while iteration < max_iterations
          iteration += 1

          # Call LLM
          response = @llm.chat(
            messages: messages,
            model: profile[:model],
            temperature: profile[:temperature],
            max_tokens: profile[:max_tokens],
            tools: tool_schemas,
            call_type: "agent",
            gmail_thread_id: gmail_thread_id
          )

          # Check if LLM wants to use tools
          if response[:tool_calls].present?
            # Process each tool call
            response[:tool_calls].each do |tool_call|
              tool_name = tool_call[:name]
              tool_args = tool_call[:arguments]

              # Execute tool
              result = Agent::ToolRegistry.instance.execute(
                tool_name,
                arguments: tool_args,
                context: { user: @user, gmail_client: @gmail_client }
              )

              # Log tool call
              agent_run.log_tool_call(
                tool_name: tool_name,
                input: tool_args,
                output: result
              )

              # Add tool call and result to conversation
              messages << { role: "assistant", content: nil, tool_calls: [tool_call] }
              messages << { role: "tool", tool_call_id: tool_call[:id], content: result.to_s }
            end
          else
            # LLM provided final answer
            final_message = response[:content]
            agent_run.complete!(final_message)

            # Log completion event
            email = @user.emails.find_by(gmail_thread_id: gmail_thread_id)
            email&.log_event("agent_completed", "Agent '#{profile_name}' completed: #{final_message&.truncate(200)}")

            return agent_run
          end
        end

        # Max iterations reached
        agent_run.max_iterations!("Reached maximum iterations (#{max_iterations})")
        email = @user.emails.find_by(gmail_thread_id: gmail_thread_id)
        email&.log_event("agent_max_iterations", "Agent '#{profile_name}' hit max iterations (#{max_iterations})")

        agent_run
      rescue StandardError => e
        agent_run.fail!(e.message)
        email = @user.emails.find_by(gmail_thread_id: gmail_thread_id)
        email&.log_event("agent_error", "Agent '#{profile_name}' error: #{e.message}")

        agent_run
      end
    end

    private

    def load_profile(name)
      profiles = AppConfig.get(:agent, :profiles) || {}
      profile_config = profiles[name] || {}

      system_prompt = load_system_prompt(profile_config["system_prompt_file"])

      {
        model: profile_config["model"] || AppConfig.llm.draft_model,
        system_prompt: system_prompt,
        tools: profile_config["tools"] || %w[create_draft escalate],
        temperature: profile_config["temperature"] || 0.3,
        max_tokens: profile_config["max_tokens"] || 4096,
        max_iterations: profile_config["max_iterations"] || DEFAULT_MAX_ITERATIONS
      }
    end

    def load_system_prompt(file_path)
      if file_path.present?
        full_path = Rails.root.join(file_path)
        return File.read(full_path) if File.exist?(full_path)
      end

      # Default agent system prompt
      <<~PROMPT
        You are an AI email assistant agent. Your job is to process incoming emails and take appropriate action.

        Guidelines:
        - Use create_draft for responses that need human review
        - Use escalate for issues beyond your capabilities
        - Be concise and professional in your responses
        - If uncertain, always err on the side of creating a draft rather than auto-sending
      PROMPT
    end
  end
end
