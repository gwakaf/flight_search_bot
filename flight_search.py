"""Flight search service."""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from amadeus_client import search_flights, check_connection

logger = logging.getLogger(__name__)

@dataclass
class FlightOffer:
    """Represents a flight offer with all relevant details."""
    price: float
    outbound_date: str
    outbound_airline: str
    outbound_departure: str
    outbound_arrival: str
    return_date: Optional[str] = None
    return_airline: Optional[str] = None
    return_departure: Optional[str] = None
    return_arrival: Optional[str] = None

@dataclass
class SearchResult:
    """Result of a flight search operation."""
    offers: List[FlightOffer]
    is_complete: bool  # Indicates if all date pairs were processed

class FlightSearchService:
    """Service for processing flight search results."""
    
    def __init__(self, search_params: Dict[str, Any]):
        """Initialize the service with search parameters."""
        self.search_params = search_params
    
    @staticmethod
    def parse_flight_offer(offer: Dict[str, Any], is_round_trip: bool = True) -> FlightOffer:
        """Parse raw flight offer into FlightOffer object."""
        price = float(offer['price']['total'])
        segments = offer['itineraries']
        
        # Parse outbound flight
        outbound = segments[0]['segments']
        outbound_data = {
            'price': price,
            'outbound_date': outbound[0]['departure']['at'].split('T')[0],
            'outbound_airline': outbound[0]['carrierCode'],
            'outbound_departure': outbound[0]['departure']['at'],
            'outbound_arrival': outbound[-1]['arrival']['at']
        }
        
        # Parse return flight if round trip
        if is_round_trip and len(segments) > 1:
            return_segments = segments[1]['segments']
            outbound_data.update({
                'return_date': return_segments[0]['departure']['at'].split('T')[0],
                'return_airline': return_segments[0]['carrierCode'],
                'return_departure': return_segments[0]['departure']['at'],
                'return_arrival': return_segments[-1]['arrival']['at']
            })
        
        return FlightOffer(**outbound_data)
    
    def generate_date_pairs(self) -> List[Tuple[str, str]]:
        """Generate date pairs for flight search."""
        date_pairs = []
        date_format = "%Y-%m-%d"
        start_date = self.search_params['start_date']
        flexibility = self.search_params['start_date_flexibility']
        min_stay, max_stay = self.search_params['stay_duration_range']
        
        # For each possible start date
        for day_offset in range(-flexibility, flexibility + 1):
            outbound_date = start_date + timedelta(days=day_offset)
            
            # For each possible stay duration
            for stay_days in range(min_stay, max_stay + 1):
                return_date = outbound_date + timedelta(days=stay_days)
                date_pairs.append((
                    outbound_date.strftime(date_format),
                    return_date.strftime(date_format)
                ))
        
        return date_pairs
    
    def search_flight_offers(self) -> SearchResult:
        """
        Search for flights using configured parameters.
        
        Returns:
            SearchResult containing offers and completion status
        """
        matching_offers = []
        date_pairs = self.generate_date_pairs()
        total_pairs = len(date_pairs)
        
        logger.info(f"Searching for {total_pairs} date combinations")
        
        for index, (outbound_date, return_date) in enumerate(date_pairs, 1):
            logger.info(f"Searching flights for {outbound_date} -> {return_date} ({index}/{total_pairs})")
            
            response = search_flights(
                origin=self.search_params['origin'],
                destination=self.search_params['destination'],
                departure_date=outbound_date,
                return_date=return_date,
                max_price=self.search_params['max_price']
            )
            
            if response:
                # Extract and parse flight offers directly
                for offer in response.get('data', []):
                    try:
                        flight = self.parse_flight_offer(offer)
                        matching_offers.append(flight)
                    except Exception as e:
                        logger.error(f"Error processing flight offer: {str(e)}")
                        continue
        
        # All date pairs have been processed
        return SearchResult(offers=matching_offers, is_complete=True)
    
    @staticmethod
    def check_connection() -> bool:
        """Check if the Amadeus API connection is working."""
        return check_connection() 