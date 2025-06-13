"""Main entry point for the flight search application."""
import os
import sys
import signal
import logging
import asyncio
from typing import Optional
import argparse
from dotenv import load_dotenv

from telegram_bot import FlightSearchBot
from flight_search import FlightSearchService
from config_loader import ConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
bot: Optional[FlightSearchBot] = None
search_service: Optional[FlightSearchService] = None

def signal_handler(signum, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {signum}")
    if bot:
        # Create a new event loop for the shutdown
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot.stop())
        finally:
            loop.close()
    sys.exit(0)

def load_and_validate_config(config_path: str):
    """Load and validate configuration."""
    try:
        config = ConfigLoader.load_config(config_path)
        search_params = ConfigLoader.get_search_params(config)
        return config, search_params
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        raise

async def run_direct_search(config_path: str):
    """Run a direct search without command interaction."""
    try:
        global bot, search_service
        
        # Load configuration
        config, search_params = load_and_validate_config(config_path)
        
        # Initialize services
        search_service = FlightSearchService(search_params)
        bot = FlightSearchBot(search_service)
        
        await bot.run_direct_search()
    except Exception as e:
        logger.error(f"Error in direct search: {str(e)}")
        if bot:
            await bot.stop()
        sys.exit(1)

async def run_normal_mode(config_path: str):
    """Run the bot in normal mode with command handling."""
    try:
        global bot, search_service
        
        # Load configuration
        config, search_params = load_and_validate_config(config_path)
        
        # Initialize services
        search_service = FlightSearchService(search_params)
        bot = FlightSearchBot(search_service)
        
        await bot.run_polling()
    except Exception as e:
        logger.error(f"Error in normal mode: {str(e)}")
        if bot:
            await bot.stop()
        sys.exit(1)

def main():
    """Main function to run the application."""
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Flight Search Bot')
        parser.add_argument('--direct', action='store_true', help='Run in direct search mode')
        parser.add_argument('--config', type=str, default='config.json', help='Path to configuration file')
        args = parser.parse_args()

        # Load environment variables
        load_dotenv()
        
        # Validate required environment variables
        required_vars = [
            'AMADEUS_CLIENT_ID',
            'AMADEUS_CLIENT_SECRET',
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID'  # Required for direct execution
        ]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            logger.error("Please set them in your .env file")
            sys.exit(1)
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Check if running in direct mode
            if args.direct:
                logger.info("Running in direct search mode...")
                loop.run_until_complete(run_direct_search(args.config))
            else:
                # Run in normal mode
                logger.info("Starting Flight Search Bot in normal mode...")
                loop.run_until_complete(run_normal_mode(args.config))
        finally:
            loop.close()
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        if bot:
            # Create a new event loop for the shutdown
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(bot.stop())
            finally:
                loop.close()

if __name__ == '__main__':
    main() 