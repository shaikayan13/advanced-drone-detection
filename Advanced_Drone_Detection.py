import cv2
import torch
import numpy as np
from PIL import Image
import ctypes
import os
import time
import threading
import sounddevice as sd

# ----------------------------
# Setup icon for separate window
# ----------------------------
img = Image.open("drone_img.png")
img.save("icon.ico", format="ICO", sizes=[(64, 64)])

# ----------------------------
# Load YOLOv5 model
# ----------------------------
model = torch.hub.load('ultralytics/yolov5', 'custom', path='best.pt', source='github')
cap = cv2.VideoCapture(0)  # use default camera
classes = ['Drone']

# ----------------------------
# Restricted area polygon
# ----------------------------
polygon_coords = [(50, 50), (250, 50), (250, 250), (50, 250)]
dragging = False
drag_index = -1

# ----------------------------
# Drone trails
# ----------------------------
drone_trails = []

# ----------------------------
# FPS calculation
# ----------------------------
prev_time = 0

# ----------------------------
# Sound detection flag
# ----------------------------
sound_detected = False

def sound_listener():
    """ Continuously listen to microphone and update sound_detected """
    global sound_detected
    fs = 44100
    duration = 1
    threshold = 0.00005

    while True:
        try:
            audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
            sd.wait()
            volume_norm = np.linalg.norm(audio) / len(audio)
            sound_detected = volume_norm > threshold
        except Exception as e:
            print("Sound error:", e)
            sound_detected = False
        time.sleep(0.1)

# ----------------------------
# Mouse callback for draggable polygon
# ----------------------------
def mouse_event(event, x, y, flags, param):
    global polygon_coords, dragging, drag_index
    if event == cv2.EVENT_LBUTTONDOWN:
        for i, corner in enumerate(polygon_coords):
            if abs(corner[0] - x) <= 10 and abs(corner[1] - y) <= 10:
                dragging = True
                drag_index = i
                break
    elif event == cv2.EVENT_LBUTTONUP:
        dragging = False
    elif event == cv2.EVENT_MOUSEMOVE and dragging:
        polygon_coords[drag_index] = (x, y)

cv2.namedWindow('Drone Detection', cv2.WINDOW_NORMAL)
cv2.setMouseCallback('Drone Detection', mouse_event)

# ----------------------------
# Set custom window icon (Windows only)
# ----------------------------
try:
    import win32gui, win32con
    hwnd = win32gui.FindWindow(None, 'Drone Detection')
    if hwnd:
        hicon = ctypes.windll.user32.LoadImageW(
            0, os.path.abspath("icon.ico"),
            win32con.IMAGE_ICON, 0, 0,
            win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
        )
        ctypes.windll.user32.SendMessageW(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, hicon)
        ctypes.windll.user32.SendMessageW(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, hicon)
except:
    pass

# ----------------------------
# Status file for visual/sound detection
# ----------------------------
STATUS_FILE = "status.txt"
def write_status(visual, sound):
    try:
        with open(STATUS_FILE, "w") as f:
            f.write(f"{int(visual)},{int(sound)}")
    except:
        pass

# ----------------------------
# Main detection loop
# ----------------------------
if __name__ == "__main__":
    threading.Thread(target=sound_listener, daemon=True).start()

    loading = True
    counter = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        img_pil = Image.fromarray(frame[..., ::-1])
        results = model(img_pil, size=640)
        drones_detected = []

        # ----------------------------
        # Drone Detection
        # ----------------------------
        for result in results.xyxy[0]:
            x1, y1, x2, y2, conf, cls = result.tolist()
            if conf > 0.5 and classes[int(cls)] in classes:
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                drones_detected.append((cx, cy))
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                cv2.putText(frame, f"{conf*100:.1f}%", (int(x1), int(y1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                drone_trails.append((cx, cy, time.time()))

        # ----------------------------
        # Check polygon (restricted area)
        # ----------------------------
        danger = False
        for cx, cy in drones_detected:
            if cv2.pointPolygonTest(np.array(polygon_coords, np.int32), (cx, cy), False) >= 0:
                danger = True
                break

        write_status(visual=danger, sound=sound_detected)

        # ----------------------------
        # Draw polygon and corners
        # ----------------------------
        overlay = frame.copy()
        if danger:
            cv2.fillPoly(overlay, [np.array(polygon_coords, np.int32)], (0, 0, 255))
            alpha = 0.3 + 0.2 * np.sin(time.time() * 5)
            frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
            # ALERT text at top
            cv2.putText(frame, "⚠ ALERT: Drone in Restricted Zone ⚠", (50, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        for i, corner in enumerate(polygon_coords):
            cv2.circle(frame, corner, 6, (0, 255, 0), -1)
            cv2.line(frame, corner, polygon_coords[(i + 1) % len(polygon_coords)], (0, 255, 0), 2)

        # ----------------------------
        # Draw drone trails (fade effect)
        # ----------------------------
        current_time = time.time()
        drone_trails = [(x, y, t) for x, y, t in drone_trails if current_time - t < 1.5]
        for x, y, t in drone_trails:
            alpha = int(255 * (1 - (current_time - t)/1.5))
            cv2.circle(frame, (x, y), 6, (0, 0, 255), -1)

        # ----------------------------
        # Loading overlay
        # ----------------------------
        if loading and counter < 30:
            overlay = frame.copy()
            cv2.putText(overlay, "Loading Drone Detection...", (50, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
            frame = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
            counter += 1
        else:
            loading = False

        # ----------------------------
        # FPS & Drone count box
        # ----------------------------
        fps = 1 / (time.time() - prev_time)
        prev_time = time.time()
        # Draw semi-transparent box
        overlay_box = frame.copy()
        cv2.rectangle(overlay_box, (10, frame.shape[0]-60), (250, frame.shape[0]-10), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay_box, 0.6, frame, 0.4, 0)
        cv2.putText(frame, f"FPS: {fps:.1f}", (20, frame.shape[0]-35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(frame, f"Drones: {len(drones_detected)}", (20, frame.shape[0]-15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # ----------------------------
        # Sound status at top right
        # ----------------------------
        sound_text = "🔊 Drone sound detected!" if sound_detected else "✅ No drone sound"
        color = (0, 0, 255) if sound_detected else (0, 255, 0)
        cv2.putText(frame, sound_text, (frame.shape[1]-350, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # ----------------------------
        # Show frame
        # ----------------------------
        cv2.imshow('Drone Detection', frame)
        if cv2.waitKey(1) == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
