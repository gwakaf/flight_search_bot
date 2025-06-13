"""Telegram bot handler for flight search commands."""
import os
import logging
from datetime import datetime
from typing import Optional, List, Union
from dataclasses import asdict
import asyncio

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

from flight_search import FlightOffer, FlightSearchService, SearchResult

logger = logging.getLogger(__name__)

class FlightSearchBot:
    """Telegram bot for handling flight search commands."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, search_service: FlightSearchService, token: Optional[str] = None, chat_id: Optional[Union[str, int]] = None):
        """Ensure only one instance of FlightSearchBot exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Initialize the instance
            cls._instance.token = token or os.getenv('TELEGRAM_BOT_TOKEN')
            cls._instance.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
            
            if not cls._instance.token:
                raise ValueError("Telegram bot token not provided")
            
            # Store search service
            cls._instance.search_service = search_service
            cls._instance.search_params = search_service.search_params
            
            cls._instance.is_stopping = False
            cls._instance.app = None
        
        return cls._instance

    async def initialize(self):
        """Initialize the bot application if not already initialized."""
        if not self._initialized:
            # Create application
            self.app = Application.builder().token(self.token).build()
            
            # Add handlers
            self.app.add_handler(CommandHandler("start", self.start_command))
            self.app.add_handler(CommandHandler("help", self.help_command))
            self.app.add_handler(CommandHandler("search", self.search_command))
            self.app.add_handler(CommandHandler("status", self.status_command))
            self.app.add_handler(CommandHandler("stop", self.stop_command))
            
            # Initialize the application
            await self.app.initialize()
            self._initialized = True

    async def run_polling(self):
        """Run the bot in polling mode."""
        if not self._initialized:
            await self.initialize()
        await self.app.start()
        await self.app.run_polling(stop_signals=None)  # We'll handle signals ourselves

    def run(self):
        """Run the bot synchronously."""
        asyncio.run(self.run_polling())
    
    @staticmethod
    def format_flight_offer(offer: FlightOffer) -> str:
        """Format flight offer for Telegram message."""
        message = [
            f"💰 Price: ${offer.price:.2f}",
            f"\n✈️ Outbound Flight:",
            f"📅 Date: {offer.outbound_date}",
            f"🛫 Departure: {offer.outbound_departure}",
            f"🛬 Arrival: {offer.outbound_arrival}",
            f"✈️ Airline: {offer.outbound_airline}"
        ]
        
        if offer.return_date:
            message.extend([
                f"\n↩️ Return Flight:",
                f"📅 Date: {offer.return_date}",
                f"🛫 Departure: {offer.return_departure}",
                f"🛬 Arrival: {offer.return_arrival}",
                f"✈️ Airline: {offer.return_airline}"
            ])
        
        return "\n".join(message)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send welcome message when /start command is issued."""
        welcome_msg = (
            "👋 Welcome to the Flight Search Bot!\n\n"
            "I can help you find the best flight deals between airports.\n\n"
            "Available commands:\n"
            "/search - Search for flights\n"
            "/status - Show current search parameters\n"
            "/help - Show this help message\n"
            "/stop - Stop the bot"
        )
        await update.message.reply_text(welcome_msg)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send help message when /help command is issued."""
        help_msg = (
            "🔍 How to use the Flight Search Bot:\n\n"
            "/search - Start a flight search with default parameters\n"
            "/status - Show current search parameters and bot status\n"
            "/stop - Stop the bot\n"
            "(SFO to OGG, ±3 days around July 31, 2025, 7-8 days stay)\n\n"
            "Example:\n"
            "/search"
        )
        await update.message.reply_text(help_msg)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show current search parameters and bot status."""
        try:
            # Check API connection through the service
            api_status = "✅ Connected" if FlightSearchService.check_connection() else "❌ Not Connected"
            
            # Format the status message
            status_msg = [
                "🤖 Flight Search Bot Status\n",
                f"API Status: {api_status}\n",
                "\n📊 Current Search Parameters:",
                f"• Origin: {self.search_params['origin']}",
                f"• Destination: {self.search_params['destination']}",
                f"• Base Date: {self.search_params['base_date'].strftime('%Y-%m-%d')}",
                f"• Days Flexibility: ±{self.search_params['days_flexibility']} days",
                f"• Stay Duration: {self.search_params['return_days'][0]}-{self.search_params['return_days'][1]} days",
                f"• Maximum Price: ${self.search_params['max_price']:.2f}"
            ]
            
            await update.message.reply_text("\n".join(status_msg))
            
        except Exception as e:
            logger.error(f"Error in status command: {str(e)}")
            await update.message.reply_text("❌ Error getting bot status")
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /search command."""
        if self.is_stopping:
            await update.message.reply_text("Bot is shutting down, cannot process new searches.")
            return

        try:
            # Send initial message
            message = await update.message.reply_text("🔍 Searching for flights...")
            
            # Search for flights using the service
            search_result = self.search_service.search_flight_offers()
            
            if not search_result.offers:
                await message.edit_text("❌ No flights found matching your criteria.")
                if search_result.is_complete:
                    await self.complete_search(update)
                return
            
            # Sort offers by price
            search_result.offers.sort(key=lambda x: x.price)
            
            # Send results
            result_msg = [
                f"✅ Found {len(search_result.offers)} matching flights!\n",
                "🏆 Best deals:\n"
            ]
            
            # Show top 5 offers
            for i, offer in enumerate(search_result.offers[:5], 1):
                result_msg.extend([
                    f"\n#{i} Deal:",
                    self.format_flight_offer(offer),
                    "\n" + "-"*30
                ])
            
            await message.edit_text("\n".join(result_msg))
            
            # If search is complete, stop the bot
            if search_result.is_complete:
                await self.complete_search(update)
            
        except Exception as e:
            logger.error(f"Error in search command: {str(e)}")
            error_msg = "❌ Sorry, something went wrong while searching for flights."
            if message:
                await message.edit_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
    
    async def complete_search(self, update: Update) -> None:
        """Handle search completion and bot shutdown."""
        if not self.is_stopping:
            self.is_stopping = True
            await update.message.reply_text("✅ Search completed! All date pairs processed. Shutting down...")
            # Use asyncio.create_task to avoid blocking
            await self.stop()
    
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Stop the bot."""
        if not self.is_stopping:
            self.is_stopping = True
            await update.message.reply_text("👋 Shutting down the bot. Goodbye!")
            await self.stop()
        
    async def direct_search(self) -> None:
        """Execute a direct search without command interaction."""
        if not self._initialized:
            await self.initialize()
            await self.app.start()

        if self.is_stopping:
            logger.info("Bot is shutting down, cannot process new searches.")
            return

        if not self.chat_id:
            logger.error("No chat ID provided for direct message sending")
            return

        try:
            # Send initial message
            message = await self.app.bot.send_message(
                chat_id=self.chat_id,
                text="🔍 Searching for flights..."
            )
            
            # Search for flights using the service
            search_result = self.search_service.search_flight_offers()
            
            if not search_result.offers:
                await self.app.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=message.message_id,
                    text="❌ No flights found matching your criteria."
                )
                if search_result.is_complete:
                    await self.app.bot.send_message(
                        chat_id=self.chat_id,
                        text="✅ Search completed! All date pairs processed. Shutting down..."
                    )
                    await self.stop()
                return
            
            # Sort offers by price
            search_result.offers.sort(key=lambda x: x.price)
            
            # Send results
            result_msg = [
                f"✅ Found {len(search_result.offers)} matching flights!\n",
                "🏆 Best deals:\n"
            ]
            
            # Show top 5 offers
            for i, offer in enumerate(search_result.offers[:5], 1):
                result_msg.extend([
                    f"\n#{i} Deal:",
                    self.format_flight_offer(offer),
                    "\n" + "-"*30
                ])
            
            await self.app.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=message.message_id,
                text="\n".join(result_msg)
            )
            
            # If search is complete, stop the bot
            if search_result.is_complete:
                await self.app.bot.send_message(
                    chat_id=self.chat_id,
                    text="✅ Search completed! All date pairs processed. Shutting down..."
                )
                await self.stop()
            
        except Exception as e:
            logger.error(f"Error in direct search: {str(e)}")
            error_msg = "❌ Sorry, something went wrong while searching for flights."
            try:
                await self.app.bot.send_message(
                    chat_id=self.chat_id,
                    text=error_msg
                )
            except Exception as send_error:
                logger.error(f"Error sending error message: {str(send_error)}")
            await self.stop()

    async def run_direct_search(self):
        """Run a direct search and initialize the bot if needed."""
        try:
            await self.direct_search()
        except Exception as e:
            logger.error(f"Error in run_direct_search: {str(e)}")
            await self.stop()

    async def stop(self):
        """Stop the bot gracefully."""
        if not self.is_stopping:
            self.is_stopping = True
            try:
                if self.app and self._initialized:
                    await self.app.stop()
                    await self.app.shutdown()
                    self._initialized = False
                logger.info("Bot has been shut down gracefully")
            except Exception as e:
                logger.error(f"Error during bot shutdown: {str(e)}") 