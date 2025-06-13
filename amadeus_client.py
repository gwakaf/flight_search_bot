"""Amadeus API client wrapper."""
import os
import logging
from typing import Optional, Dict, Any
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# Initialize the Amadeus client at module level
client_id = os.getenv('AMADEUS_CLIENT_ID')
client_secret = os.getenv('AMADEUS_CLIENT_SECRET')

if not client_id or not client_secret:
    raise ValueError("Amadeus credentials not provided")

class _AmadeusClient:
    """Internal Amadeus API client."""
    
    def __init__(self):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = None
    
    def _get_access_token(self) -> Optional[str]:
        """Get or refresh Amadeus access token."""
        try:
            # Check if current token is still valid
            if self.access_token and self.token_expires_at:
                if datetime.now() < self.token_expires_at:
                    return self.access_token
            
            # Get new token
            token_url = 'https://test.api.amadeus.com/v1/security/oauth2/token'
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            # Set token expiration (subtract 5 minutes for safety margin)
            self.token_expires_at = datetime.now().fromtimestamp(
                datetime.now().timestamp() + token_data['expires_in'] - 300
            )
            
            return self.access_token
            
        except Exception as e:
            logger.error(f"Failed to get access token: {str(e)}")
            if hasattr(response, 'text'):
                logger.error(f"Response: {response.text}")
            return None

# Create a single instance of the client
_client = _AmadeusClient()

def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    adults: int = 1,
    max_results: int = 250,
    non_stop: bool = True,
    currency: str = 'USD',
    max_price: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """
    Search for flight offers using the Amadeus API.
    
    Args:
        origin: Origin airport code (e.g., 'SFO')
        destination: Destination airport code (e.g., 'OGG')
        departure_date: Departure date in YYYY-MM-DD format
        return_date: Optional return date for round trips
        adults: Number of adult passengers
        max_results: Maximum number of results to return
        non_stop: Whether to search for non-stop flights only
        currency: Currency code for prices
        max_price: Maximum price filter for the API
        
    Returns:
        Complete API response as dictionary or None if request failed
    """
    try:
        # Get fresh token
        access_token = _client._get_access_token()
        if not access_token:
            return None
        
        # Set up request
        url = 'https://test.api.amadeus.com/v2/shopping/flight-offers'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'originLocationCode': origin,
            'destinationLocationCode': destination,
            'departureDate': departure_date,
            'adults': str(adults),
            'max': str(max_results),
            'nonStop': 'true' if non_stop else 'false',
            'currencyCode': currency
        }
        
        # Add return date for round trips
        if return_date:
            params['returnDate'] = return_date
            
        # Add max price if specified - convert to integer string
        if max_price is not None:
            params['maxPrice'] = str(int(max_price))
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        if hasattr(response, 'text'):
            logger.error(f"Response: {response.text}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in flight search: {str(e)}")
        return None

def check_connection() -> bool:
    """Check if we can connect to the Amadeus API."""
    return _client._get_access_token() is not None 