#!/usr/bin/env python3
# presence_system.py - Main launcher for Sabrina's Presence System

import sys
import os
import argparse
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from presence_enhancements import EnhancedPresenceGUI

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Sabrina AI Presence System")
    parser.add_argument("--theme", help="Start with a specific theme", default="default")
    parser.add_argument("--animation", help="Start with a specific animation state", default="idle")
    parser.add_argument("--minimized", help="Start minimized to system tray", action="store_true")
    parser.add_argument("--transparent", help="Enable transparent background", action="store_true")
    parser.add_argument("--opacity", help="Set initial opacity (10-100)", type=int, default=85)
    parser.add_argument("--test", help="Run animation test mode", action="store_true")
    return parser.parse_args()

def run_presence_system():
    """Run the Sabrina AI Presence System."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Create QApplication instance
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Prevent app from quitting when window is closed
    
    # Create presence GUI
    presence = EnhancedPresenceGUI()
    
    # Apply command line settings
    if args.theme != "default":
        presence.change_theme(args.theme)
    
    if args.animation != "idle":
        presence.set_animation(args.animation)
    
    if args.transparent:
        presence.setAttribute(Qt.WA_TranslucentBackground)
    
    if args.opacity:
        opacity = max(10, min(100, args.opacity))  # Keep between 10-100
        presence.setWindowOpacity(opacity / 100)
        presence.transparency_slider.setValue(opacity)
    
    # Show window unless minimized flag is set
    if not args.minimized:
        presence.show()
    
    # If test mode is enabled, run the animation test sequence
    if args.test:
        print("Running in test mode!")
        run_animation_test(presence)
    
    # Start the application event loop
    sys.exit(app.exec_())

def run_animation_test(presence):
    """Run a test sequence of animations."""
    from PyQt5.QtCore import QTimer
    
    # Get all animation states
    states = presence.animation_manager.get_available_states()
    print(f"Available animations: {', '.join(states)}")
    
    # Create a test sequence
    test_sequence = ["idle", "listening", "talking", "working", "thinking", 
                     "error", "success", "waiting", "idle"]
    current_index = 0
    
    def next_animation():
        nonlocal current_index
        if current_index < len(test_sequence):
            state = test_sequence[current_index]
            print(f"Setting animation: {state}")
            presence.set_animation(state)
            current_index += 1
            QTimer.singleShot(3000, next_animation)  # 3 second delay
        else:
            print("Animation test completed")
    
    # Start the test sequence
    QTimer.singleShot(1000, next_animation)  # 1 second initial delay

if __name__ == "__main__":
    # Set working directory to script location for asset loading
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    run_presence_system()