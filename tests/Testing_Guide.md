# Sabrina AI User Testing Guide

## Introduction

This guide will help you test the Sabrina AI system's functionality, ensuring all components work correctly together. It covers the various capabilities and provides step-by-step instructions for verifying each feature.

## Prerequisites

Before testing, ensure you have:

1. Installed all dependencies as per the installation instructions
2. Set up the required hardware (microphone, speakers)
3. Started all necessary services using the launcher script

## Basic Testing Flow

### 1. System Startup

```bash
# Linux/macOS
./scripts/sabrina_ai_launcher.sh start all

# Windows
scripts\sabrina_ai_launcher_windows.bat start all
```

Verify that:
- The voice service starts without errors
- The core system initializes properly
- The presence module appears (if enabled)

### 2. Voice Interaction Testing

1. **Wake Word Detection**
   - Say "Hey Sabrina" and verify the system enters the listening state
   - Check that the presence animation changes to the listening state

2. **Basic Commands**
   - Ask "What time is it?" to test basic functionality
   - Ask "How are you?" to test system status responses
   - Say "Goodbye" to verify session ending behavior

3. **Speech Synthesis**
   - Instruct "Say hello world" to test voice output
   - Check that the text is spoken clearly through your speakers
   - Observe the presence animation changing to the speaking state

### 3. Vision System Testing

1. **Screen Capture**
   - Ask "Capture the screen" and verify a screenshot is taken
   - Examine the saved image in the data/captures directory

2. **OCR Functionality**
   - Open a text document or webpage
   - Ask "What does the screen say?" or "Read the screen"
   - Verify that text is properly extracted and reported

3. **UI Element Detection**
   - Open an application with clear UI elements (buttons, menus)
   - Ask "What elements do you see on the screen?"
   - Verify detection of major UI components

### 4. Automation Testing

1. **Mouse Control**
   - Ask "Click at the center of the screen"
   - Verify the mouse moves and clicks at the specified position

2. **Keyboard Input**
   - Open a text editor
   - Say "Type hello from Sabrina AI"
   - Verify the text is typed correctly

3. **Combined Operations**
   - Ask to "Open Notepad, type a greeting, and save the file"
   - Verify the sequence completes successfully

### 5. Smart Home Integration (if configured)

1. **Device Status**
   - Ask "What smart devices are available?"
   - Verify the system lists your configured devices

2. **Device Control**
   - Request "Turn on the living room light"
   - Verify the device state changes as expected

## Error Handling Testing

1. **Invalid Commands**
   - Say something unintelligible or give an impossible command
   - Verify appropriate error handling and recovery

2. **Service Interruption**
   - Stop one service (e.g., `./scripts/sabrina_ai_launcher.sh stop voice`)
   - Verify system identifies and reports the missing service
   - Restart the service and verify recovery

## Advanced Testing Scenarios

1. **Multi-turn Conversations**
   - Initiate a task that requires multiple exchanges
   - Verify conversation context is maintained

2. **Concurrent Operations**
   - Request multiple actions in sequence without waiting
   - Verify proper handling of the command queue

3. **Resource Usage**
   - Monitor CPU, memory, and GPU usage during typical operations
   - Verify the system remains within acceptable resource limits

## Logging and Troubleshooting

- Check the logs at `logs/sabrina.log` for errors or warnings
- Use the status command to check service health:
  ```bash
  ./scripts/sabrina_ai_launcher.sh status
  ```

# Test Implementation Todo List

Based on the current test files and structure, here are the tests that still need to be implemented:

## 1. Unit Tests

- [ ] **Component Service Wrappers**: More complete unit tests for each service wrapper:
  - [ ] Complete `VisionService` unit tests
  - [ ] Complete `HearingService` unit tests
  - [ ] Complete `PresenceService` unit tests
  - [ ] Complete `SmartHomeService` unit tests

- [ ] **LLM Integration Framework**:
  - [ ] Tests for `LLMInputHandler` class
  - [ ] Tests for function registration and execution
  - [ ] Tests for input/output type handling

- [ ] **Enhanced Event System**:
  - [ ] Edge case handling for high-volume events
  - [ ] Priority-based event processing

- [ ] **Memory System**:
  - [ ] Tests for storage and retrieval operations
  - [ ] Tests for context management

## 2. Integration Tests

- [ ] **Voice-Automation Integration**:
  - [ ] Voice commands triggering automation actions
  - [ ] Error handling between services

- [ ] **Vision-Automation Integration**:
  - [ ] OCR-based automation
  - [ ] UI element detection followed by automated interaction

- [ ] **LLM-Component Communication**:
  - [ ] Test the flow from LLM input to component actions
  - [ ] Test component results flowing back to LLM

- [ ] **Smart Home Integration**:
  - [ ] Smart device discovery and control
  - [ ] Home automation routines

- [ ] **State Machine Integration**:
  - [ ] Tests for complex state transitions
  - [ ] Event-triggered state changes

## 3. End-to-End Tests

- [ ] **Conversation Flow Testing**:
  - [ ] Multi-turn conversational interactions
  - [ ] Context preservation during extended interactions

- [ ] **Full Command Execution Flows**:
  - [ ] Voice command → Understanding → Action → Feedback cycle
  - [ ] Text command → Understanding → Action → Feedback cycle

- [ ] **System Recovery Tests**:
  - [ ] Service failure and recovery
  - [ ] Unexpected shutdown handling

## 4. Performance Tests

- [ ] **Latency Measurements**:
  - [ ] Voice processing response time
  - [ ] Automation execution time

- [ ] **Resource Usage Tests**:
  - [ ] Memory consumption over time
  - [ ] CPU utilization under various loads
  - [ ] GPU usage patterns

## 5. Test Infrastructure Improvements

- [ ] **Mocking Framework Enhancements**:
  - [ ] More robust component mocks for test independence
  - [ ] Standard mock behaviors for predictable testing

- [ ] **Test Data Generation**:
  - [ ] Test data generators for various components
  - [ ] Realistic sample inputs for various scenarios

- [ ] **Continuous Integration Setup**:
  - [ ] GitHub Actions workflow for automated testing
  - [ ] Test coverage reporting

## 6. Documentation and Test Organization

- [ ] **Test Case Documentation**:
  - [ ] Complete test case descriptions and expected outcomes
  - [ ] Test coverage mapping to features

- [ ] **Test Environment Setup**:
  - [ ] Containerized test environment
  - [ ] Reproducible testing configuration

## Priority Implementation Order

1. Complete core unit tests (Essential functionality)
2. Implement basic integration tests (Component interactions)
3. Build end-to-end tests for critical flows (User experience validation)
4. Add performance and resource usage tests (Production readiness)
5. Enhance test infrastructure and documentation (Maintainability)

Would you like me to elaborate on any specific area of the testing plan or user testing guide?
