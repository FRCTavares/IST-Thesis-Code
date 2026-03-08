import cv2
import time

cap = cv2.VideoCapture("/dev/video0", cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"UYVY"))

if not cap.isOpened():
    print("FAILED: could not open /dev/video0")
    raise SystemExit(1)

t0 = time.time()
ok_count = 0
first_saved = False

for i in range(30):
    ok, frame = cap.read()
    print(f"frame {i}: ok={ok}", flush=True)
    if not ok:
        break
    ok_count += 1
    if not first_saved:
        cv2.imwrite("/tmp/tevs_first_frame.png", frame)
        first_saved = True

t1 = time.time()
cap.release()

dt = t1 - t0
fps = ok_count / dt if dt > 0 else 0.0
print(f"captured={ok_count}, elapsed={dt:.3f}s, approx_fps={fps:.2f}")
print("saved=/tmp/tevs_first_frame.png")