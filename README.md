# Discord Auto Messenger Bot

## Overview

This tool automates sending messages in Discord servers using multiple tokens. The bot can:
- Send predefined or randomly generated messages
- Reply to existing messages using Gemini AI
- Use proxy servers for distribution
- Auto-manage messaging frequency with break times

## Features

- **Multiple Token Support**: Run multiple Discord accounts simultaneously
- **AI-Powered Messaging**: Uses Google's Gemini AI to generate conversational messages
- **Smart Conversation**: Can reply to existing messages to appear more natural
- **Proxy Support**: Distribute requests through different proxies
- **Break Management**: Automatically takes breaks to avoid detection
- **Server Configuration**: Target specific servers and channels

## Installation

### Prerequisites

- Python 3.7 or higher
- A Discord account with tokens
- A Gemini API key

### Setup

1. Clone or download this repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Configure the `config.json` file (see Configuration section)
4. (Optional) Add proxies to `proxies.txt` file

## Configuration

Create a `config.json` file based on the `config_example.json` template:

```json
{
  "gemini_api_key": "Your Gemini API Key",
  "servers": [
      {
          "server_id": 12345678,
          "channel_id": 12345678,
          "mention_id": 0
      }
  ],
  "tokens": [
      "Your Discord token 1",
      "Your Discord token 2"
  ],
  "message_count": 10,
  "time_delay": 5,
  "language": "English",
  "list_message": [
    "Message 1",
    "Message 2",
    "Message 3"
  ]
}
```

### Configuration Parameters

- `gemini_api_key`: Your Google Gemini API key for AI message generation
- `servers`: Array of server configurations
  - `server_id`: Discord server ID
  - `channel_id`: Channel ID within the server
  - `mention_id`: User ID to mention (0 for no mention)
- `tokens`: Array of Discord account tokens
- `message_count`: Number of messages before taking a break
- `time_delay`: Break duration in minutes
- `language`: Language for auto generate (English, Japan, Việt Nam,...)
- `list_message`: Array of predefined messages to send

## Message Configuration

The bot supports multiple ways to configure messages:

### 1. Simple Message List

You can provide a simple list of messages that all bots will share:

```json
{
  "list_message": [
    "Hello everyone!",
    "How's it going?",
    "Just checking in!",
    "What's new today?"
  ]
}
```

With this configuration, each bot will randomly select messages from the entire list.

### 2. Bot-Specific Message Groups

You can assign specific messages to specific bots by using nested arrays:

```json
{
  "list_message": [
    ["Bot 1's message 1", "Bot 1's message 2"],
    ["Bot 2's message 1", "Bot 2's message 2"],
    ["Bot 3's message 1"]
  ]
}
```

In this configuration:
- The first bot will only use messages from the first nested array
- The second bot will only use messages from the second nested array
- The third bot will only use messages from the third nested array

If you have more bots than message groups, the additional bots will use the entire message list.

### 3. Mixed Configuration

You can also mix individual messages with grouped messages:

```json
{
  "list_message": [
    ["Bot 1 message 1", "Bot 1 message 2"],
    "This is a message for Bot 2",
    ["Bot 3 message 1", "Bot 3 message 2"]
  ]
}
```

In this case:
- Bot 1 will use the first array of messages
- Bot 2 will use only the single message "This is a message for Bot 2"
- Bot 3 will use the second array of messages

This gives you complete flexibility in how messages are distributed among your bots.

## Proxy Configuration

Add proxies to `proxies.txt` in the format:
```
http://username:password@ip:port
or
http://ip:port
```

One proxy per line. Dead proxies will be moved to `proxies_die.txt` automatically.

## Usage

Run the bot with:

```bash
python main.py
```

When prompted, decide whether to send messages randomly or sequentially:
- `Y` (default): Send messages in random order
- `N`: Send messages in the order they appear in the configuration

## How It Works

1. The bot logs into Discord using the provided tokens
2. It alternates between:
   - Sending new messages from the predefined list
   - Replying to existing messages using Gemini AI
3. After sending `message_count` messages, it takes a break for `time_delay` minutes
4. Messages are sent with random delays (1-2 minutes) to appear more natural

## Safety and Best Practices

- Use this tool responsibly and in accordance with Discord's Terms of Service
- Avoid sending too many messages in a short period
- Use different tokens and proxies to distribute the load
- Keep break times reasonable to avoid detection

## Troubleshooting

- If tokens are not working, verify they are still valid
- If proxies are not working, they will be automatically moved to `proxies_die.txt`
- Check the console output for detailed error messages

## Disclaimer

This tool is for educational purposes only. Use it at your own risk and responsibility.