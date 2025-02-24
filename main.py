import cv2
import mediapipe as mp
import numpy as np
import requests
import hashlib
import re
import time
from flask import Flask, render_template, Response, jsonify

app = Flask(__name__)

# Initialize MediaPipe Hand Tracking
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.6
)

# Virtual Keyboard Configuration
keys = list("1234567890QWERTYUIOPASDFGHJKLZXCVBNM")
keyboard_size = (800, 300)
key_size = (50, 50)

# Global variables
typed_chars = ""
last_key_time = time.time()
typing_finished = False
key_press_delay = 5  # 5-second delay between key presses
is_waiting = False  # Flag to indicate if we're waiting for the delay to complete

def is_palm_closed(hand_landmarks):
    """Detect if the palm is closed (all fingers are curled in)"""
    finger_tips = [
        hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP],
        hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP],
        hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP],
        hand_landmarks.landmark[mp_hands.HandLandmark.RING_FINGER_TIP],
        hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_TIP]
    ]

    finger_pips = [
        hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_IP],
        hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_PIP],
        hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_PIP],
        hand_landmarks.landmark[mp_hands.HandLandmark.RING_FINGER_PIP],
        hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_PIP]
    ]

    return all(tip.y > pip.y for tip, pip in zip(finger_tips, finger_pips))

def assess_password_strength(password):
    """Evaluate password strength"""
    score = 0
    feedback = []

    if len(password) >= 8:
        score += 1
        feedback.append("Good length")
    if re.search(r"[A-Z]", password):
        score += 1
        feedback.append("Has uppercase")
    if re.search(r"[a-z]", password):
        score += 1
        feedback.append("Has lowercase")
    if re.search(r"\d", password):
        score += 1
        feedback.append("Has numbers")
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        score += 1
        feedback.append("Has special chars")

    ratings = {
        1: "Very Weak",
        2: "Weak",
        3: "Moderate",
        4: "Strong",
        5: "Very Strong"
    }
    return ratings.get(score, "Very Weak"), feedback

def check_password_leaked(password):
    """Check if password appears in breached databases"""
    sha1_pass = hashlib.sha1(password.encode()).hexdigest().upper()
    first5, rest = sha1_pass[:5], sha1_pass[5:]
    try:
        response = requests.get(f"https://api.pwnedpasswords.com/range/{first5}")
        for line in response.text.splitlines():
            hash_suffix, count = line.split(":")
            if hash_suffix == rest:
                return True, int(count)
        return False, 0
    except:
        return None, 0

def draw_virtual_keyboard(frame):
    """Draw the virtual keyboard on the frame"""
    for i, key in enumerate(keys):
        x = (i % 10) * key_size[0] + 50
        y = (i // 10) * key_size[1] + 50
        cv2.rectangle(frame, (x, y), (x + key_size[0], y + key_size[1]), (200, 200, 200), -1)
        cv2.putText(frame, key, (x + 15, y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    # Draw instruction text
    cv2.putText(frame, "Point with index finger to type", (50, 280),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(frame, "Close palm to finish typing", (50, 310),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    if typing_finished:
        cv2.putText(frame, "Typing Complete!", (50, 350),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

    return frame

def generate_frames():
    """Generate video frames with virtual keyboard and hand tracking"""
    global typed_chars, last_key_time, typing_finished, is_waiting
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open webcam")
        return

    while True:
        success, frame = cap.read()
        if not success:
            break

        # Flip frame horizontally for mirror effect
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb_frame)

        # Draw keyboard
        frame = draw_virtual_keyboard(frame)

        # Process hand landmarks
        if result.multi_hand_landmarks and not typing_finished:
            for hand_landmarks in result.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                if is_palm_closed(hand_landmarks):
                    typing_finished = True
                    break

                # Get index finger tip position
                index_finger_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
                h, w, _ = frame.shape
                ix, iy = int(index_finger_tip.x * w), int(index_finger_tip.y * h)

                # Check for key presses (only if not waiting for the delay to complete)
                if not is_waiting:
                    for i, key in enumerate(keys):
                        x = (i % 10) * key_size[0] + 50
                        y = (i // 10) * key_size[1] + 50
                        if x < ix < x + key_size[0] and y < iy < y + key_size[1]:
                            typed_chars += key
                            last_key_time = time.time()
                            is_waiting = True  # Start waiting for 5 seconds
                else:
                    # Check if the 5-second delay has passed
                    if time.time() - last_key_time >= key_press_delay:
                        is_waiting = False  # Reset the waiting flag

        # Convert frame to JPEG format
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()
@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_typing_status')
def get_typing_status():
    """Return typing status and password analysis"""
    global typed_chars, typing_finished, last_key_time, is_waiting

    if not typed_chars:
        return jsonify({
            'password': '',
            'strength': 'Not enough characters',
            'feedback': [],
            'leaked': False,
            'leak_count': 0,
            'is_waiting': is_waiting,
            'last_key_time': last_key_time
        })

    strength, feedback = assess_password_strength(typed_chars)
    leaked, leak_count = check_password_leaked(typed_chars)

    return jsonify({
        'finished': typing_finished,
        'password': typed_chars,
        'strength': strength,
        'feedback': feedback,
        'leaked': leaked,
        'leak_count': leak_count,
        'is_waiting': is_waiting,
        'last_key_time': last_key_time
    })

@app.route('/reset_typing', methods=['POST'])
def reset_typing():
    """Reset the typing process"""
    global typed_chars, typing_finished, is_waiting
    typed_chars = ""
    typing_finished = False
    is_waiting = False
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True)