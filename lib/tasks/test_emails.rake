# frozen_string_literal: true

namespace :test_emails do
  desc "Send synthetic test emails. Usage: rake test_emails:send[recipient@example.com,needs_response,formal,1]"
  task :send, [:recipient, :classification, :style, :count] => :environment do |_t, args|
    recipient = args[:recipient]
    classification = args[:classification] || "needs_response"
    style = args[:style] || "formal"
    count = (args[:count] || 1).to_i

    unless recipient
      puts "\e[31mUsage: rake test_emails:send[recipient@example.com,classification,style,count]\e[0m"
      puts ""
      puts "Classifications: needs_response, action_required, payment_request, fyi, waiting"
      puts "Styles: formal, casual, terse, verbose, passive_aggressive, friendly"
      exit 1
    end

    user = User.first
    unless user
      puts "\e[31mERROR: No users found.\e[0m"
      exit 1
    end

    puts "\e[36m=== Test Email Sender ===\e[0m"
    puts "Recipient: #{recipient}"
    puts "Classification target: #{classification}"
    puts "Style: #{style}"
    puts "Count: #{count}"
    puts ""

    gmail_client = Gmail::Client.new(user: user)

    count.times do |i|
      email_content = generate_test_email(classification, style, i + 1)

      begin
        # Create a raw RFC 2822 message
        raw_message = build_raw_message(
          from: user.email,
          to: recipient,
          subject: email_content[:subject],
          body: email_content[:body]
        )

        gmail_client.send_message(raw_message)
        puts "\e[32m  Sent #{i + 1}/#{count}: #{email_content[:subject]}\e[0m"

        # Delay between emails
        if i < count - 1
          delay = 5
          puts "  Waiting #{delay}s before next email..."
          sleep(delay)
        end
      rescue Gmail::Client::GmailApiError => e
        puts "\e[31m  Failed to send email #{i + 1}: #{e.message}\e[0m"
      end
    end

    puts ""
    puts "\e[32mDone. #{count} test email(s) sent.\e[0m"
  end

  desc "Generate test email content without sending. Usage: rake test_emails:preview[classification,style]"
  task :preview, [:classification, :style] => :environment do |_t, args|
    classification = args[:classification] || "needs_response"
    style = args[:style] || "formal"

    puts "\e[36m=== Test Email Preview ===\e[0m"
    puts "Classification: #{classification}"
    puts "Style: #{style}"
    puts ""

    content = generate_test_email(classification, style, 1)
    puts "Subject: #{content[:subject]}"
    puts ""
    puts content[:body]
  end
end

def generate_test_email(classification, style, number)
  templates = {
    "needs_response" => {
      subjects: [
        "Question about project timeline",
        "Can you review this document?",
        "Need your input on the proposal",
        "Follow-up on our conversation",
        "Quick question about the budget"
      ],
      bodies: {
        "formal" => "Dear colleague,\n\nI hope this message finds you well. I would like to inquire about the current status of the project timeline. Could you please provide an update at your earliest convenience?\n\nI look forward to hearing from you.\n\nBest regards",
        "casual" => "Hey!\n\nJust checking in - how's the project going? Any updates on the timeline? Would be great to get a quick status update when you get a chance.\n\nThanks!",
        "terse" => "Project timeline update?\n\nNeed status ASAP.",
        "verbose" => "Hello,\n\nI wanted to reach out regarding several items that have been on my mind concerning the project. First, I'd like to discuss the timeline and whether we're still on track for the Q2 deliverables. Additionally, I have some concerns about the resource allocation that I think we should address sooner rather than later. There's also the matter of the budget review that was supposed to happen last week.\n\nCould we schedule some time to discuss all of this?\n\nMany thanks",
        "passive_aggressive" => "Hi,\n\nAs I mentioned in my previous three emails, I still haven't received an update on the project timeline. I'm sure you've been very busy, but it would be really nice to know where things stand. Just whenever you get a moment, of course.\n\nThanks so much",
        "friendly" => "Hi there!\n\nHope you're having a great week! I was wondering if you had a chance to look at the project timeline. No rush at all, just wanted to touch base and see how things are progressing.\n\nHave a wonderful day!"
      }
    },
    "action_required" => {
      subjects: [
        "Meeting invitation: Q2 Planning",
        "Action needed: Document review by Friday",
        "Please approve the budget request",
        "Calendar invite: Team sync tomorrow"
      ],
      bodies: {
        "formal" => "Dear team,\n\nPlease find attached the Q2 planning document. Your review and approval is required by end of day Friday.\n\nRegards",
        "casual" => "Hey team,\n\nMeeting tomorrow at 2pm for Q2 planning. Please add it to your calendar. See you there!",
        "terse" => "Review attached doc. Approval needed by Friday.",
        "verbose" => "Hello everyone,\n\nI'm writing to let you know that we have scheduled the Q2 planning session. The meeting will take place tomorrow at 2:00 PM in the main conference room. Please come prepared with your department updates and any concerns.\n\nAgenda items include budget review, resource allocation, and timeline adjustments.\n\nLooking forward to a productive discussion.",
        "passive_aggressive" => "Hi,\n\nJust a friendly reminder (again) that the document review is due by Friday. I know everyone's calendar is packed, but this really can't wait any longer.\n\nThanks",
        "friendly" => "Hi everyone!\n\nExciting news - we have our Q2 planning meeting set up! Looking forward to hearing everyone's ideas. See you all at 2pm tomorrow!"
      }
    },
    "payment_request" => {
      subjects: [
        "Invoice #12345 - Payment due",
        "Subscription renewal - Action required",
        "Outstanding balance notification",
        "Payment reminder: Service fees"
      ],
      bodies: {
        "formal" => "Dear valued customer,\n\nPlease find below the details for Invoice #12345:\n\nAmount due: $2,450.00\nDue date: End of month\nPayment reference: INV-2024-12345\n\nPlease arrange payment at your earliest convenience.\n\nAccounts Receivable Department",
        "casual" => "Hi!\n\nJust a heads up that your invoice for $2,450 is ready. Due by end of month. Let me know if you have any questions!\n\nCheers",
        "terse" => "Invoice #12345. Amount: $2,450.00. Due: EOM. Pay promptly.",
        "verbose" => "Dear customer,\n\nWe are writing to inform you that Invoice #12345, dated today, is now available for your review. The total amount due is $2,450.00, which covers the services rendered during the previous billing period. Payment is expected by the end of the current month.\n\nAccepted payment methods include bank transfer, credit card, and check. Please reference the invoice number when making payment.\n\nShould you have any questions or require clarification regarding any line items, please do not hesitate to contact our accounting department.\n\nThank you for your business.",
        "passive_aggressive" => "Hi,\n\nThis is the third reminder about Invoice #12345 ($2,450.00). I'm sure it's just an oversight, but payment was actually due two weeks ago. We'd really appreciate it if this could be taken care of soon.\n\nThanks",
        "friendly" => "Hey!\n\nHope you're doing well! Quick note - we've sent over Invoice #12345 for $2,450. No rush, just wanted to make sure it's on your radar. Due by end of month. Thanks so much!"
      }
    },
    "fyi" => {
      subjects: [
        "Newsletter: Weekly tech digest",
        "Your order has been shipped",
        "System maintenance scheduled",
        "New feature announcement"
      ],
      bodies: {
        "formal" => "Dear subscriber,\n\nThis is to inform you that scheduled maintenance will take place this weekend from Saturday 10 PM to Sunday 6 AM. During this time, some services may be temporarily unavailable.\n\nWe apologize for any inconvenience.\n\nOperations Team",
        "casual" => "Hey!\n\nJust wanted to let you know we shipped your order today. Tracking number: TRK-123456. Should arrive in 3-5 business days.\n\nCheers!",
        "terse" => "System maintenance Saturday 10PM-Sunday 6AM. Services may be unavailable.",
        "verbose" => "Dear valued customer,\n\nWe are pleased to inform you that your recent order has been processed and shipped. Your tracking number is TRK-123456. You can track your package on our website. Estimated delivery is within 3-5 business days depending on your location.\n\nThank you for choosing our service.",
        "passive_aggressive" => "Hi,\n\nJust FYI, we're doing system maintenance this weekend. Again. Hopefully this time it won't take longer than scheduled.\n\nOperations",
        "friendly" => "Great news! Your order is on its way! Tracking: TRK-123456. Can't wait for you to receive it!"
      }
    },
    "waiting" => {
      subjects: [
        "Re: Project proposal feedback",
        "Re: Waiting for your response",
        "Re: Document review request",
        "Re: Follow-up on our meeting"
      ],
      bodies: {
        "formal" => "Dear colleague,\n\nThank you for your message. I have forwarded your request to the relevant department and am awaiting their response. I will get back to you as soon as I have an update.\n\nBest regards",
        "casual" => "Thanks for the heads up! I've passed it along and am waiting to hear back. Will keep you posted!",
        "terse" => "Noted. Waiting on response from team. Will update.",
        "verbose" => "Thank you for reaching out about this matter. I want to assure you that I have taken note of all the points you raised and have already begun the process of gathering the necessary information. I have reached out to the relevant team members and am currently awaiting their input before I can provide you with a comprehensive response.",
        "passive_aggressive" => "Thanks for the follow-up. I did send the request over to the team last week as promised. Still waiting to hear back from them. I'll let you know when I know something.",
        "friendly" => "Thanks for reaching out! I'm on it - just waiting to hear back from the team. Will let you know as soon as I have something!"
      }
    }
  }

  template = templates[classification] || templates["needs_response"]
  subject_index = (number - 1) % template[:subjects].size
  subject = template[:subjects][subject_index]
  body = template[:bodies][style] || template[:bodies]["formal"]

  # Add some uniqueness
  subject = "#{subject} (##{number})" if number > 1

  { subject: subject, body: body }
end

def build_raw_message(from:, to:, subject:, body:)
  message = <<~MESSAGE
    From: #{from}
    To: #{to}
    Subject: #{subject}
    Content-Type: text/plain; charset=UTF-8
    Date: #{Time.current.rfc2822}

    #{body}
  MESSAGE

  Base64.urlsafe_encode64(message)
end
