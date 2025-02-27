#!/usr/bin/env python3
"""
Component Integration Example for Sabrina AI
===========================================
This script demonstrates the integration of key Sabrina AI components
using the enhanced core and voice client.
"""

import os
import sys
import time
import logging
import argparse

# Ensure the project directory is in the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger("integration_example")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Sabrina AI Component Integration Example")
    parser.add_argument("--config", type=str, default="config/settings.yaml", help="Path to configuration file")
    parser.add_argument("--voice-only", action="store_true", help="Demonstrate only voice component")
    parser.add_argument("--vision-only", action="store_true", help="Demonstrate only vision component")
    parser.add_argument("--full", action="store_true", help="Demonstrate full integration")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()

def setup_directories():
    """Ensure required directories exist"""
    dirs = ["logs", "data", "config"]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def create_default_config():
    """Create default configuration if it doesn't exist"""
    config_path = "config/settings.yaml"
    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            f.write("""
# Sabrina AI Configuration

core:
  debug_mode: false
  log_level: INFO
  enabled_components:
    - voice
    - vision
    - hearing
    - automation

voice:
  enabled: true
  api_url: http://localhost:8100
  volume: 0.8
  speed: 1.0
  pitch: 1.0
  emotion: normal

vision:
  enabled: true
  capture_method: auto
  use_ocr: true
  use_object_detection: false
  max_images: 5

hearing:
  enabled: true
  wake_word: hey sabrina
  silence_threshold: 0.03
  model_path: models/vosk-model
  use_hotkey: true
  hotkey: ctrl+shift+s

automation:
  enabled: true
  mouse_move_duration: 0.2
  typing_interval: 0.1
  failsafe: true

memory:
  max_entries: 20
  use_vector_db: false
  vector_db_path: data/vectordb

smart_home:
  enable: false
  home_assistant_url: http://homeassistant.local:8123
  
presence:
  enable: false
  theme: default
  transparency: 0.85
  click_through: false
""")
        logger.info(f"Created default configuration at {config_path}")

def demonstrate_voice_only():
    """Demonstrate voice component functionality"""
    from services.voice.enhanced_voice_client import EnhancedVoiceClient
    from utilities.event_system import EventBus, EventType, Event, EventPriority
    
    logger.info("Starting voice component demonstration")
    
    # Create event bus
    event_bus = EventBus()
    event_bus.start()
    
    # Handle voice status events
    def handle_voice_status(event):
        status = event.data.get("status", "")
        text = event.data.get("text", "")
        logger.info(f"Voice status: {status}, Text: {text[:30]}...")
    
    # Register event handler
    event_bus.register_handler(
        event_bus.create_event_handler(
            event_types=[EventType.VOICE_STATUS],
            callback=handle_voice_status
        )
    )
    
    # Create voice client
    try:
        voice_client = EnhancedVoiceClient(api_url="http://localhost:8100", event_bus=event_bus)
    except Exception as e:
        logger.error(f"Failed to create voice client: {str(e)}")
        event_bus.stop()
        return
    
    # Check connection
    if not voice_client.connected:
        logger.error("Voice API not connected - make sure the voice service is running")
        event_bus.stop()
        return
    
    # Demo script
    try:
        print("Voice Component Demonstration")
        print("============================")
        
        print("\n1. Basic speech synthesis...")
        voice_client.speak("Hello! I'm Sabrina, your personal AI assistant. Let me demonstrate my voice capabilities.")
        time.sleep(3)
        
        print("\n2. Speech with different emotions...")
        voice_client.set_emotion("happy")
        voice_client.speak("I can speak with different emotions, like happiness!")
        time.sleep(2)
        
        voice_client.set_emotion("sad")
        voice_client.speak("Or sadness, if that's what the situation calls for.")
        time.sleep(2)
        
        voice_client.set_emotion("normal")
        voice_client.speak("And back to my normal voice.")
        time.sleep(2)
        
        print("\n3. Speech with different speeds...")
        voice_client.set_speed(0.8)
        voice_client.speak("I can slow down my speaking rate when needed.")
        time.sleep(2)
        
        voice_client.set_speed(1.5)
        voice_client.speak("Or I can speed up when time is of the essence!")
        time.sleep(2)
        
        voice_client.set_speed(1.0)
        voice_client.speak("And back to my normal speed.")
        time.sleep(2)
        
        print("\n4. Using event system for speech...")
        event_bus.post_event(
            Event(
                event_type=EventType.VOICE,
                data={
                    "text": "I can also be triggered through the event system, which enables better component integration.",
                    "settings": {"emotion": "excited"}
                },
                source="demonstration"
            )
        )
        time.sleep(3)
        
        print("\nVoice component demonstration complete!")
        voice_client.speak("Voice component demonstration complete! Thank you for listening.")
        
    except KeyboardInterrupt:
        print("\nDemonstration interrupted.")
    except Exception as e:
        logger.error(f"Error in voice demonstration: {str(e)}")
    finally:
        # Stop event bus
        event_bus.stop()

def demonstrate_vision_only():
    """Demonstrate vision component functionality"""
    from services.vision.vision_core import VisionCore
    from utilities.event_system import EventBus, EventType, Event, EventPriority
    
    logger.info("Starting vision component demonstration")
    
    # Create event bus
    event_bus = EventBus()
    event_bus.start()
    
    # Handle vision events
    def handle_vision_event(event):
        cmd = event.data.get("command", "")
        image_path = event.data.get("image_path", "")
        ocr_text = event.data.get("ocr_text", "")
        logger.info(f"Vision event: {cmd}, Image: {image_path}, OCR: {ocr_text[:30]}...")
    
    # Register event handler
    event_bus.register_handler(
        event_bus.create_event_handler(
            event_types=[EventType.VISION],
            callback=handle_vision_event
        )
    )
    
    # Create vision client
    try:
        vision_core = VisionCore()
    except Exception as e:
        logger.error(f"Failed to create vision component: {str(e)}")
        event_bus.stop()
        return
    
    # Demo script
    try:
        print("Vision Component Demonstration")
        print("=============================")
        
        print("\n1. Basic screen capture...")
        print("Capturing screen in 3 seconds (position your windows as desired)...")
        time.sleep(3)
        
        # Perform screen capture
        try:
            # Try to import CaptureMode enum
            try:
                from services.vision.constants import CaptureMode
                mode = CaptureMode.FULL_SCREEN
            except ImportError:
                mode = "full_screen"
                
            image_path = vision_core.capture_screen(mode)
            print(f"Screen captured successfully: {image_path}")
            
            # Post vision event
            event_bus.post_event(
                Event(
                    event_type=EventType.VISION,
                    data={
                        "command": "capture",
                        "image_path": image_path
                    },
                    source="demonstration"
                )
            )
            
            # Run OCR on the captured image
            ocr_text = vision_core.vision_ocr.run_ocr(image_path)
            
            # Print OCR results
            if ocr_text:
                print("\n2. OCR Results:")
                print("==============")
                print(ocr_text[:500] + ("..." if len(ocr_text) > 500 else ""))
                
                # Post OCR results as event
                event_bus.post_event(
                    Event(
                        event_type=EventType.VISION,
                        data={
                            "command": "ocr",
                            "image_path": image_path,
                            "ocr_text": ocr_text
                        },
                        source="demonstration"
                    )
                )
            else:
                print("\nNo text detected in the captured image.")
            
            # Demonstrate getting active window info if available
            if hasattr(vision_core, 'get_active_window_info'):
                print("\n3. Active Window Information:")
                print("===========================")
                window_info = vision_core.get_active_window_info()
                if window_info:
                    for key, value in window_info.items():
                        print(f"{key}: {value}")
                else:
                    print("No active window information available.")
                    
        except Exception as e:
            print(f"Error during screen capture: {str(e)}")
            
        print("\nVision component demonstration complete!")
        
    except KeyboardInterrupt:
        print("\nDemonstration interrupted.")
    except Exception as e:
        logger.error(f"Error in vision demonstration: {str(e)}")
    finally:
        # Stop event bus
        event_bus.stop()

def demonstrate_full_integration():
    """Demonstrate full integration of Sabrina AI components"""
    # Import the enhanced Sabrina Core
    from core.enhanced_sabrina_core import SabrinaCore, CoreState, CoreEventType
    from utilities.event_system import EventType, Event, EventPriority
    
    logger.info("Starting full integration demonstration")
    
    # Check if the voice API is running
    import requests
    voice_api_running = False
    try:
        response = requests.get("http://localhost:8100/status", timeout=1)
        voice_api_running = response.status_code == 200
    except:
        pass
    
    if not voice_api_running:
        logger.warning("Voice API not running - speech synthesis will not work")
        print("WARNING: Voice API is not running. Start it with: python services/voice/voice_api.py")
        print("Continuing with limited functionality...\n")
    
    # Create Sabrina Core instance
    core = SabrinaCore()
    
    # Check which components were successfully initialized
    available_components = list(core.components.keys())
    print("Initialized Components:")
    print("======================")
    for component in available_components:
        if component not in ["config_manager", "error_handler", "event_bus"]:
            print(f"- {component}")
    print()
    
    # Create event monitoring
    def log_events(event):
        logger.debug(f"Event: {event.event_type}, Source: {event.source}, Priority: {event.priority}")
    
    # Register general event handler
    core.event_bus.register_handler(
        core.event_bus.create_event_handler(
            event_types=None,  # All event types
            callback=log_events,
            min_priority=EventPriority.LOW
        )
    )
    
    # Demo script
    try:
        print("Full Integration Demonstration")
        print("=============================")
        print("\nThis demonstration will show the integration between components.")
        print("The system will perform a series of commands and interactions.")
        print("\nPress Ctrl+C at any time to stop the demonstration.")
        
        # Wait for user to be ready
        input("\nPress Enter to begin...")
        
        # Welcome message
        print("\n1. Voice output test...")
        core.speak("Hello! I'm Sabrina, your AI assistant. Let me show you what I can do.", 
                  {"emotion": "happy"})
        time.sleep(3)
        
        # Screen capture if vision component is available
        if "vision" in core.components:
            print("\n2. Vision component test...")
            core.process_command("!capture")
            time.sleep(3)
            
            # Process the captured data
            if "last_ocr_text" in core.context:
                ocr_preview = core.context["last_ocr_text"][:100] + "..." if len(core.context["last_ocr_text"]) > 100 else core.context["last_ocr_text"]
                core.speak(f"I can see text on your screen. For example: {ocr_preview}")
                time.sleep(3)
        
        # Automation if component is available
        if "automation" in core.components:
            print("\n3. Automation component test...")
            core.speak("I can also control your mouse and keyboard. I'll move your mouse cursor to the center of the screen.")
            time.sleep(1)
            
            # Get screen dimensions
            import pyautogui
            screen_width, screen_height = pyautogui.size()
            
            # Move mouse to center
            print("Moving mouse to screen center...")
            core.process_command(f"!move {screen_width//2} {screen_height//2}")
            time.sleep(2)
        
        # Natural language processing
        print("\n4. Natural language command processing...")
        core.speak("I also understand natural language commands. For example, when you say 'capture the screen', I'll know what to do.")
        time.sleep(2)
        
        # Process natural language command
        result, response = core.process_command("capture the screen")
        print(f"Response: {response}")
        time.sleep(3)
        
        # Demonstrate state changes
        print("\n5. System state management...")
        core.speak("I maintain an internal state to track what I'm doing.")
        time.sleep(1)
        
        # Show state changes
        print("Recent state changes:")
        for idx, state_change in enumerate(core.state_changes[-5:]):
            print(f"  {idx+1}. {state_change['from'].name} -> {state_change['to'].name}")
        
        # Memory system demonstration
        print("\n6. Memory system...")
        core.speak("I can remember our conversations and use that context later.")
        
        # Show recent memory entries
        print("Recent memory entries:")
        for idx, entry in enumerate(core.history[-6:]):
            role = entry.get("role", "unknown")
            content = entry.get("content", "")
            print(f"  {idx+1}. {role}: {content[:50]}...")
        time.sleep(2)
        
        # Wrap up
        print("\nFull integration demonstration complete!")
        core.speak("Thank you for exploring Sabrina AI's capabilities. This demonstration is now complete.", 
                  {"emotion": "happy"})
        
    except KeyboardInterrupt:
        print("\nDemonstration interrupted.")
    except Exception as e:
        logger.error(f"Error in full integration demonstration: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Shutdown core
        core._shutdown()

def main():
    """Main function"""
    # Parse arguments
    args = parse_arguments()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Setup environment
    setup_directories()
    create_default_config()
    
    # Run appropriate demonstration
    if args.voice_only:
        demonstrate_voice_only()
    elif args.vision_only:
        demonstrate_vision_only()
    elif args.full:
        demonstrate_full_integration()
    else:
        # Default to voice-only demonstration
        demonstrate_voice_only()

if __name__ == "__main__":
    main()