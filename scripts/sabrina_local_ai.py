import subprocess
import platform
import json
import os
import time
from TTS.api import TTS
from pydub import AudioSegment
from ollama import Client  # Connect with AI model

# Paths
settings_file = "voice_settings.json"
history_file = "conversation_history.json"
memory_file = "long_term_memory.json"
defaults_file = "default_memory.json"
output_dir = os.path.join(os.getcwd(), "audio_output")
os.makedirs(output_dir, exist_ok=True)

# Initialize AI model
ollama = Client()

# Default settings
DEFAULT_SETTINGS = {"speed": 1.0, "emotion": "neutral", "pitch": 1.0}

def load_defaults():
    if os.path.exists(defaults_file):
        with open(defaults_file, "r") as f:
            return json.load(f)
    return {}

def load_settings():
    if os.path.exists(settings_file):
        with open(settings_file, "r") as f:
            settings = json.load(f)
        return {**DEFAULT_SETTINGS, **settings}  # Merge defaults with stored settings
    return DEFAULT_SETTINGS

def save_settings(settings):
    with open(settings_file, "w") as f:
        json.dump(settings, f)

def load_history():
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            history = json.load(f)
        return history if history else []
    return []

def save_history(history):
    with open(history_file, "w") as f:
        json.dump(history, f)

def load_memory():
    if os.path.exists(memory_file):
        with open(memory_file, "r") as f:
            return json.load(f)
    return load_defaults()  # Use default memory as fallback

def save_memory(memory):
    with open(memory_file, "w") as f:
        json.dump(memory, f, indent=4)

def update_history(user_input, ai_response):
    history = load_history()
    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": ai_response})
    save_history(history[-10:])  # Keep only the last 10 exchanges

def process_command(command):
    settings = load_settings()
    parts = command.split()
    if len(parts) == 2 and parts[0] in ["!speed", "!emotion", "!pitch"]:
        key = parts[0][1:]
        try:
            value = float(parts[1]) if key in ["speed", "pitch"] else parts[1]
            settings[key] = value
            save_settings(settings)
            return f"Updated {key} to {value}"
        except ValueError:
            return "Invalid value!"
    elif command == "!reset":
        save_settings(DEFAULT_SETTINGS)
        return "Voice settings reset!"
    elif command == "!forget":
        save_history([])
        return "Chat history cleared!"
    return "Unknown command."

def ask_sabrina(user_input):
    """
    Sends a prompt to the locally running Mistral-7B model via Ollama.
    """
    memory = load_memory()  # Load long-term memory
    history = load_history()  # Load recent chat history
    
    context = f"""
    You are Sabrina, a confident, witty AI assistant who loves gaming, AI embodiment, and interacting with Eric.
    Your personality is engaging, strategic, and playful. 
    You remember past interactions and help Eric with AI development, smart home automation, and gaming strategies.
    """
    
    if memory:
        context += f"\nHere’s what you know about Eric:\n{json.dumps(memory, indent=2)}"
    
    if history:
        context += f"\nRecent conversation history:\n{json.dumps(history[-5:], indent=2)}"  # Include only last 5 messages for context.
    
    context += "\nNow respond naturally to his latest message."
    
    response = ollama.chat(model='mistral', messages=[
        {"role": "system", "content": context},
        {"role": "user", "content": user_input}
    ])
    
    # Save response to chat history
    if 'message' in response and 'content' in response['message']:
        update_history(user_input, response['message']['content'])
        return response['message']['content']
    return "Error: No response generated."

def speak(text):
    if text.startswith("!"):
        print(process_command(text))
        return
    
    settings = load_settings()
    ai_response = ask_sabrina(text)
    
    timestamp = int(time.time())
    output_file = os.path.join(output_dir, f"response_{timestamp}.wav")
    
    tts = TTS("tts_models/en/jenny/jenny", gpu=True)
    
    tts.tts_to_file(
        text=ai_response,
        file_path=output_file,
        speed=settings["speed"],  
        emotion=settings["emotion"]
    )
    
    if platform.system() == "Windows":
        process = subprocess.Popen([
            "ffplay", "-nodisp", "-autoexit", output_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        process = subprocess.Popen(["afplay", output_file])
    
    process.wait()
    time.sleep(0.5)
    try:
        os.remove(output_file)
    except PermissionError:
        print(f"Warning: Unable to delete {output_file}. It might still be in use.")

def main():
    print("Sabrina is ready. Type your message or some commands like '!speed 1.2', '!emotion happy', '!forget'. Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break
        speak(user_input)

if __name__ == "__main__":
    main()
