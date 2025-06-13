# Flight Search Bot

A serverless Telegram bot for searching flights using the Amadeus API. The bot is built using AWS Lambda, API Gateway, and SAM (Serverless Application Model).

## Features

- Automated flight search with configurable parameters
- Telegram bot interface with command support
- Dual operation modes: interactive and direct execution
- Automatic completion and graceful shutdown
- Configurable search parameters via JSON configuration
- AWS Lambda + API Gateway serverless deployment
- Real-time flight availability and pricing
- Serverless architecture for cost efficiency
- CloudWatch logging for monitoring and debugging
- Secure configuration management using S3

## Project Structure

```
.
├── src/                  # Lambda function source code
│   ├── lambda_handler.py # AWS Lambda handlers
│   ├── flight_search.py  # Flight search service
│   ├── telegram_bot.py   # Telegram bot implementation
│   ├── config_loader.py  # Configuration loading
│   └── requirements.txt  # Python dependencies
├── template.yaml         # AWS SAM template
├── deploy.sh            # Deployment script
├── config.json          # Search parameters configuration
└── README.md            # This file
```

## Prerequisites

- AWS CLI installed and configured
- AWS SAM CLI installed
- Python 3.9 or later
- Telegram Bot Token (from BotFather)
- Amadeus API credentials

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd flight-search-bot
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file with your credentials:
```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Amadeus API Configuration
AMADEUS_CLIENT_ID=your_client_id
AMADEUS_CLIENT_SECRET=your_client_secret
```

## Deployment

The application is deployed using AWS SAM. The deployment script (`deploy.sh`) handles the entire process:

1. Validates environment variables and AWS credentials
2. Creates necessary S3 buckets for deployment and configuration
3. Uploads configuration files
4. Builds and deploys the application

To deploy:

```bash
# Deploy to dev environment
./deploy.sh dev

# Force redeploy (deletes existing stack)
./deploy.sh dev true
```

The deployment will create:
- Lambda function for handling Telegram webhook events
- API Gateway for receiving webhook requests
- IAM roles with necessary permissions
- S3 buckets for configuration and deployment
- CloudWatch Log Groups for monitoring

## Architecture

### Components

1. **Lambda Function (`InteractiveSearchFunction`)**
   - Handles Telegram webhook events
   - Processes flight search requests
   - Integrates with Amadeus API
   - Writes logs to CloudWatch

2. **API Gateway**
   - Receives webhook requests from Telegram
   - Routes requests to Lambda function
   - Handles CORS and request validation

3. **IAM Roles**
   - `InteractiveSearchFunctionRole`: Grants permissions for:
     - CloudWatch Logs access
     - S3 bucket access
     - Lambda execution

4. **S3 Buckets**
   - Deployment bucket: Stores SAM deployment artifacts
   - Config bucket: Stores application configuration

### Logging

The application uses CloudWatch Logs for monitoring and debugging. Log groups are automatically created with the following naming convention:
- `/aws/lambda/flight-search-bot-{stage}-InteractiveSearchFunction`

## Usage

1. After deployment, the script will output the webhook URL
2. Set up the webhook for your Telegram bot:
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=<WEBHOOK_URL>"
```

3. Start using the bot in Telegram:
   - Send `/start` to begin
   - Use `/help` to see available commands
   - Follow the interactive prompts to search for flights

## Troubleshooting

### Common Issues

1. **Deployment Fails**
   - Check AWS credentials in `.env` file
   - Ensure all required environment variables are set
   - Check CloudFormation console for detailed error messages

2. **No Logs in CloudWatch**
   - Verify Lambda function execution role has CloudWatch Logs permissions
   - Check if the function is being invoked (test with a message to the bot)
   - Ensure the function is writing logs using the Python logging module

3. **Webhook Not Working**
   - Verify the webhook URL is correctly set in Telegram
   - Check API Gateway logs for any errors
   - Ensure the Lambda function is returning the correct response format

### Debugging

1. Check CloudWatch Logs:
   - Open AWS Console
   - Navigate to CloudWatch > Log Groups
   - Find the log group for your function
   - Check for any error messages or exceptions

2. Test Lambda Function:
   - Use AWS Console to test the function directly
   - Check the test event response
   - Verify environment variables are set correctly

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Configuration Parameters

### Flight Search Parameters
- `origin`: Origin airport code (e.g., "SFO")
- `destination`: Destination airport code (e.g., "OGG")
- `start_date`: Base date to start searching from (YYYY-MM-DD)
- `start_date_flexibility`: Number of days to search before and after start date (e.g., 3 means ±3 days)
- `stay_duration`: Trip length configuration
  - `min_days`: Minimum number of days to stay
  - `max_days`: Maximum number of days to stay
- `max_price`: Maximum price in specified currency
- `currency`: Currency code (e.g., "USD")
- `adults`: Number of adult passengers
- `max_results`: Maximum number of results per search
- `nonStop`: Whether to search for non-stop flights only

### Example Search Pattern
With the default configuration:
- Start dates: July 28 - August 3, 2025 (±3 days around July 31)
- For each start date:
  - Try 7-day stay
  - Try 8-day stay
- Total combinations: 14 date pairs (7 possible start dates × 2 stay durations)

## Error Handling

The application includes comprehensive error handling:
- API connection issues
- Configuration validation
- Lambda function timeouts
- S3 access errors
- Telegram API errors

## Monitoring and Logging

- CloudWatch Logs for Lambda functions
- CloudWatch Metrics for API Gateway
- X-Ray tracing (optional)
- Custom metrics for search results

## Development

To contribute:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License 