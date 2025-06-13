"""Configuration loader for the flight search application."""
import json
import os
from datetime import datetime
from typing import Dict, Any

class ConfigLoader:
    """Handles loading and validating configuration from JSON file."""
    
    @staticmethod
    def load_config(config_path: str = "config.json") -> Dict[str, Any]:
        """Load configuration from JSON file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Convert date string to datetime
        if 'flight_search' in config:
            start_date = config['flight_search'].get('start_date')
            if start_date:
                config['flight_search']['start_date'] = datetime.strptime(start_date, "%Y-%m-%d")
                
        return config
    
    @staticmethod
    def get_search_params(config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract search parameters from config."""
        if 'flight_search' not in config:
            raise ValueError("Flight search configuration not found in config file")
            
        search_config = config['flight_search']
        
        return {
            'origin': search_config['origin'],
            'destination': search_config['destination'],
            'start_date': search_config['start_date'],
            'start_date_flexibility': search_config['start_date_flexibility'],
            'stay_duration_range': [
                search_config['stay_duration']['min_days'],
                search_config['stay_duration']['max_days']
            ],
            'max_price': float(search_config['max_price'])
        } 