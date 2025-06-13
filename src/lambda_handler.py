"""AWS Lambda handlers for flight search bot."""
import os
import json
import logging
import boto3
from typing import Dict, Any, Optional
import pathlib
import uuid

from flight_search import FlightSearchService
from telegram_bot import FlightSearchBot
from config_loader import ConfigLoader

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Add a test log message at module level
logger.info("Lambda handler module loaded")

# Default configuration values
DEFAULT_CONFIG_PATH = 'config.json'

def setup_logging(context) -> str:
    """Set up structured logging with request ID."""
    if context:
        request_id = context.aws_request_id
    else:
        request_id = str(uuid.uuid4())
    
    # Create a formatter that includes the request ID
    formatter = logging.Formatter(
        '[%(levelname)s] %(asctime)s - RequestId: %(request_id)s - %(message)s'
    )
    
    # Add request ID to all log records
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = request_id
        return record
    logging.setLogRecordFactory(record_factory)
    
    # Update the root logger's handler
    for handler in logger.handlers:
        handler.setFormatter(formatter)
    
    return request_id

def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment:
    1. Try S3 if CONFIG_BUCKET is set
    2. Fall back to local config.json
    3. Fall back to default config dict
    """
    logger.info("Starting to load configuration")
    # Try to load from S3 if CONFIG_BUCKET is set
    config_bucket = os.environ.get('CONFIG_BUCKET')
    if config_bucket:
        try:
            logger.info(f"Loading config from S3 bucket: {config_bucket}")
            s3 = boto3.client('s3')
            response = s3.get_object(Bucket=config_bucket, Key='config.json')
            config_str = response['Body'].read().decode('utf-8')
            logger.info("Successfully loaded config from S3")
            return json.loads(config_str)
        except Exception as e:
            logger.error(f"Error loading config from S3: {str(e)}", exc_info=True)
            logger.info("Falling back to local config.json")
    
    # Try to load from local file
    config_path = pathlib.Path(DEFAULT_CONFIG_PATH)
    if config_path.exists():
        logger.info(f"Loading local config from: {config_path}")
        with open(config_path, 'r') as f:
            config = json.load(f)
            logger.info("Successfully loaded local config")
            return config
    
    # Return default config
    logger.warning("Using default configuration")
    return {
        "flight_search": {
            "origin": "SFO",
            "destination": "OGG",
            "start_date": "2025-07-31",
            "start_date_flexibility": 3,
            "stay_duration": {
                "min_days": 7,
                "max_days": 8
            },
            "max_price": 500,
            "currency": "USD",
            "adults": 1,
            "max_results": 50,
            "nonStop": False
        },
        "telegram": {
            "chat_id": os.environ.get('TELEGRAM_CHAT_ID')
        }
    }

def get_credentials() -> Dict[str, str]:
    """Get API credentials from environment variables."""
    logger.info("Getting credentials from environment variables")
    credentials = {
        'telegram_bot_token': os.environ.get('TELEGRAM_BOT_TOKEN', ''),
        'telegram_chat_id': os.environ.get('TELEGRAM_CHAT_ID', ''),
        'amadeus_client_id': os.environ.get('AMADEUS_CLIENT_ID', ''),
        'amadeus_client_secret': os.environ.get('AMADEUS_CLIENT_SECRET', '')
    }
    
    # Log which credentials are present/missing
    for key, value in credentials.items():
        if value:
            logger.info(f"Found {key}")
        else:
            logger.warning(f"Missing {key}")
    
    return credentials

def handle_command(command: str, search_service: FlightSearchService, 
                  search_params: Dict[str, Any]) -> Optional[str]:
    """Handle bot commands and return response text."""
    if command == '/search':
        logger.info("Executing flight search")
        search_result = search_service.search_flight_offers()
        if search_result.offers:
            search_result.offers.sort(key=lambda x: x.price)
            return search_service.format_flight_offer(search_result.offers[0])
        return "No flights found matching criteria"
    
    elif command == '/status':
        logger.info("Generating status response")
        return (
            f"Current search parameters:\n"
            f"• Origin: {search_params['origin']}\n"
            f"• Destination: {search_params['destination']}\n"
            f"• Start Date: {search_params['start_date'].strftime('%Y-%m-%d')}\n"
            f"• Flexibility: ±{search_params['start_date_flexibility']} days\n"
            f"• Stay Duration: {search_params['stay_duration_range'][0]}-"
            f"{search_params['stay_duration_range'][1]} days\n"
            f"• Max Price: ${search_params['max_price']}"
        )
    
    elif command in ['/start', '/help']:
        logger.info("Generating help response")
        return (
            "Welcome to Flight Search Bot!\n\n"
            "Available commands:\n"
            "/search - Search for flights\n"
            "/status - Show current search parameters\n"
            "/help - Show this help message"
        )
    
    return None

def create_error_response(message: str) -> Dict[str, Any]:
    """Create a standardized error response."""
    return {
        'statusCode': 500,
        'body': json.dumps({
            'status': 'error',
            'message': message
        }),
        'headers': {'Content-Type': 'application/json'}
    }

def telegram_webhook_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Telegram webhook events."""
    # Set up logging with request ID
    request_id = setup_logging(context)
    logger.info(f"Received webhook event. RequestId: {request_id}")
    
    try:
        # Parse webhook data
        body = json.loads(event['body'])
        logger.info(f"Parsed webhook body: {json.dumps(body)}")
        
        # Load configuration
        config = load_config()
        search_params = ConfigLoader.get_search_params(config)
        logger.info("Configuration loaded successfully")
        
        # Get credentials
        credentials = get_credentials()
        
        # Validate credentials
        missing_credentials = [k for k, v in credentials.items() if not v]
        if missing_credentials:
            return create_error_response(f"Missing credentials: {', '.join(missing_credentials)}")
        
        # Add credentials to search parameters
        search_params['amadeus_client_id'] = credentials['amadeus_client_id']
        search_params['amadeus_client_secret'] = credentials['amadeus_client_secret']
        
        # Initialize services
        logger.info("Initializing services")
        search_service = FlightSearchService(search_params)
        bot = FlightSearchBot(search_service)
        bot.telegram_token = credentials['telegram_bot_token']
        bot.telegram_chat_id = credentials['telegram_chat_id']
        logger.info("Services initialized successfully")
        
        # Process update
        update = body.get('message', {})
        chat_id = update.get('chat', {}).get('id')
        text = update.get('text', '')
        
        if not chat_id:
            return create_error_response("No chat ID in webhook data")
        
        logger.info(f"Processing message from chat {chat_id}: {text}")
        
        # Handle commands
        if text.startswith('/'):
            command = text.split()[0].lower()
            response_text = handle_command(command, search_service, search_params)
            
            # Send response if any
            if response_text:
                logger.info("Sending response to Telegram")
                bot.app.bot.send_message(
                    chat_id=chat_id,
                    text=response_text,
                    parse_mode='HTML'
                )
                logger.info("Response sent successfully")
        
        logger.info("Webhook processing completed successfully")
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'ok'})
        }
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return create_error_response(str(e))
    finally:
        # Cleanup resources
        try:
            if 'bot' in locals():
                logger.info("Cleaning up bot resources")
                bot.app.stop()
                logger.info("Bot resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)

# For local testing
if __name__ == "__main__":
    try:
        print("Testing Telegram webhook handler...")
        # Create a test event simulating a /help command
        test_event = {
            'body': json.dumps({
                'message': {
                    'chat': {
                        'id': os.environ.get('TELEGRAM_CHAT_ID', '12345')
                    },
                    'text': '/help'
                }
            })
        }
        response = telegram_webhook_handler(test_event, None)
        print(f"Status code: {response['statusCode']}")
        print(f"Response: {response['body']}")
    except KeyboardInterrupt:
        print("\nReceived interrupt signal. Cleaning up...")
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        print("Cleanup complete.") 