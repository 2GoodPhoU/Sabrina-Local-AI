#!/usr/bin/env python3
"""
Entry point for Sabrina's Presence System
Simple launcher script that can be run directly
"""
import os
import sys
import logging

# Ensure the parent directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import our main module
from services.presence.presence_system import PresenceSystem

if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run the presence system
    presence_system = PresenceSystem()
    sys.exit(presence_system.run())