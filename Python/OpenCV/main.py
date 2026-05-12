import cv2, numpy as np, serial, threading
from flask import Flask, jsonify, request
from flask_cors import CORS

shared_data = {"ball_x": 320}
is_dead_status = 0

app = Flask(__name__)
CORS(app)

cap = cv2.VideoCapture(2, cv2.CAP_DSHOW)
cap.set(3, 640) 
cap.set(4, 480)

try:
    arduino = serial.Serial('COM3', 115200, timeout=0)
    print("Arduino Connected!")
except:
    arduino = None

#
# Main loop for OpenCV. Detect ball position using HSV mask
# and handles communication with the Arduino.
# Parameters: No
# Returns: void
#
def vision_worker():
    global is_dead_status
    lower_ball = np.array([0, 79, 175])
    upper_ball = np.array([30, 255, 255])

    while True:
        ret, frame = cap.read()
        if not ret: break

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower_ball, upper_ball)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > 300:
                M = cv2.moments(c)
                if M['m00'] > 0:
                    ball_x = int(M['m10'] / M['m00'])
                    shared_data["ball_x"] = ball_x
                    if arduino:
                        arduino.write(f"{ball_x},{is_dead_status}\n".encode())

        # Läs seriell data
        if arduino and arduino.in_waiting > 0:
            line = arduino.readline().decode('utf-8', errors='ignore').strip()
            if line:
                if line.isdigit(): shared_data["ball_x"] = int(line)
                print(f"Arduino: {line}")

        cv2.imshow("Stream", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

#
# API: Returns the current ball X-koordinat
# Return: JSON with ball_x
#
@app.route('/get_ball')
def get_ball():
    return jsonify(shared_data)

#
# API: Updates death status and notifies Arduino
# Parameter: dead, 1 for dead, 0 for alive
# Return: string "OK"
#
@app.route('/set_status')
def set_status():
    global is_dead_status
    is_dead_status = int(request.args.get('dead', 0))
    if arduino:
        arduino.write(b"D\n" if is_dead_status == 1 else b"L\n")
    return "OK"

#
# API: Sending a point trigger signal to Arduino
# Return: string "OK"
#
@app.route('/trigger_point')
def trigger_point():
    if arduino: arduino.write(b"P\n")
    return "OK"

if __name__ == '__main__':
    threading.Thread(target=vision_worker, daemon=True).start()
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    print("Server startad: http://localhost:5000")
    app.run(port=5000, threaded=True)