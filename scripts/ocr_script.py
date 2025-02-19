import cv2
import pytesseract
import numpy as np
import mss

# Set Tesseract Path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def capture_screen():
    with mss.mss() as sct:
        screenshot = sct.grab(sct.monitors[1])  # Capture primary screen
        img = np.array(screenshot)

        # Convert to grayscale for better OCR accuracy
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Run OCR
        extracted_text = pytesseract.image_to_string(gray)

        print("\n=== Extracted Text from Screen ===\n")
        print(extracted_text)

        # Show the captured screen
        cv2.imshow("Screen Capture", gray)
        cv2.waitKey(1000)  # Display for 1 second
        cv2.destroyAllWindows()

capture_screen()
