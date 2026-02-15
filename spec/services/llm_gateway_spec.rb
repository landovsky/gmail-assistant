# frozen_string_literal: true

require 'rails_helper'

RSpec.describe LlmGateway do
  let(:gateway) { described_class.new }
  let(:user) { create(:user) }

  # Mock RubyLLM::Message response matching the real API
  let(:mock_response) do
    double('RubyLLM::Message',
           content: '{"category": "needs_response"}',
           input_tokens: 100,
           output_tokens: 50,
           tool_calls: nil)
  end

  let(:mock_chat) do
    double('RubyLLM::Chat').tap do |chat|
      allow(chat).to receive(:with_instructions).and_return(chat)
      allow(chat).to receive(:with_temperature).and_return(chat)
      allow(chat).to receive(:with_params).and_return(chat)
      allow(chat).to receive(:with_schema).and_return(chat)
      allow(chat).to receive(:ask).and_return(mock_response)
    end
  end

  before do
    allow(RubyLLM).to receive(:chat).and_return(mock_chat)
  end

  describe '#chat' do
    let(:messages) do
      [
        { role: 'system', content: 'You are a classifier.' },
        { role: 'user', content: 'Classify this email.' }
      ]
    end

    it 'makes a successful API call and returns parsed response' do
      result = gateway.chat(
        model: 'gemini-2.0-flash',
        messages: messages,
        user: user,
        call_type: 'classify'
      )

      expect(result[:response_text]).to eq('{"category": "needs_response"}')
      expect(result[:prompt_tokens]).to eq(100)
      expect(result[:completion_tokens]).to eq(50)
      expect(result[:total_tokens]).to eq(150)
    end

    it 'strips provider prefix from model name' do
      gateway.chat(
        model: 'gemini/gemini-2.0-flash',
        messages: messages,
        user: user,
        call_type: 'classify'
      )

      expect(RubyLLM).to have_received(:chat).with(model: 'gemini-2.0-flash')
    end

    it 'sets system prompt via with_instructions' do
      gateway.chat(
        model: 'gemini-2.0-flash',
        messages: messages,
        user: user,
        call_type: 'classify'
      )

      expect(mock_chat).to have_received(:with_instructions).with('You are a classifier.')
    end

    it 'sets temperature' do
      gateway.chat(
        model: 'gemini-2.0-flash',
        messages: messages,
        temperature: 0.5,
        user: user,
        call_type: 'classify'
      )

      expect(mock_chat).to have_received(:with_temperature).with(0.5)
    end

    it 'logs the call to LlmCall table' do
      expect do
        gateway.chat(
          model: 'gemini-2.0-flash',
          messages: messages,
          user: user,
          call_type: 'classify'
        )
      end.to change(LlmCall, :count).by(1)

      call = LlmCall.last
      expect(call.call_type).to eq('classify')
      expect(call.model).to eq('gemini-2.0-flash')
      expect(call.system_prompt).to eq('You are a classifier.')
      expect(call.user_message).to eq('Classify this email.')
      expect(call.prompt_tokens).to eq(100)
    end

    context 'when rate limited' do
      before do
        allow(mock_chat).to receive(:ask).and_raise(
          RubyLLM::RateLimitError.new(nil, 'Rate limit exceeded')
        )
      end

      it 'raises RateLimitError and logs the failure' do
        expect do
          gateway.chat(model: 'test', messages: messages, user: user, call_type: 'classify')
        end.to raise_error(LlmGateway::RateLimitError)

        call = LlmCall.last
        expect(call.error).to include('Rate limit')
      end
    end

    context 'when timeout' do
      before do
        allow(mock_chat).to receive(:ask).and_raise(
          Faraday::TimeoutError.new('Request timeout')
        )
      end

      it 'raises TimeoutError' do
        expect do
          gateway.chat(model: 'test', messages: messages, user: user, call_type: 'classify')
        end.to raise_error(LlmGateway::TimeoutError)
      end
    end

    context 'when other RubyLLM error' do
      before do
        allow(mock_chat).to receive(:ask).and_raise(
          RubyLLM::Error.new(nil, 'API error')
        )
      end

      it 'raises LlmError' do
        expect do
          gateway.chat(model: 'test', messages: messages, user: user, call_type: 'classify')
        end.to raise_error(LlmGateway::LlmError, /API error/)
      end
    end
  end

  describe '#chat_json' do
    let(:messages) { [{ role: 'user', content: 'test' }] }

    it 'returns parsed JSON response' do
      result = gateway.chat_json(
        model: 'test',
        messages: messages,
        user: user,
        call_type: 'classify'
      )

      expect(result[:parsed_response]).to eq({ 'category' => 'needs_response' })
    end

    it 'passes JSON mode and max_tokens as provider-native params for Gemini' do
      gateway.chat_json(
        model: 'gemini-2.0-flash',
        messages: messages,
        max_tokens: 256,
        user: user,
        call_type: 'classify'
      )

      expect(mock_chat).to have_received(:with_params).with(
        generationConfig: { maxOutputTokens: 256, responseMimeType: 'application/json' }
      )
    end

    it 'passes JSON mode as response_format for OpenAI models' do
      gateway.chat_json(
        model: 'gpt-4o',
        messages: messages,
        user: user,
        call_type: 'classify'
      )

      expect(mock_chat).to have_received(:with_params).with(
        response_format: { type: 'json_object' }
      )
    end
  end
end
