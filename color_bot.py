"""
Ultra Light Trigger Bot — Potato PC Optimized
- Screen 1/4 size pe process karta hai
- No heavy morphology
- Overlay minimal
- F10 = ON/OFF | F7 = Quit
"""

import cv2
import numpy as np
import mss
import keyboard
import threading
import time
import ctypes
import winsound

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
FPS          = 40
OVERLAY_FPS  = 15
SCALE        = 0.5          # 35 se 50% — better detection, still fast
DETECTION_FOV = 280         # half-size around crosshair; smaller capture = more game FPS
KEY          = 'k'
TOGGLE_KEY   = 'f10'
QUIT_KEY     = 'f7'

# FPS-first overrides. Keep the visual overlay off unless you press F9.
SCALE        = 0.5
DETECTION_FOV = 240
SHOW_OVERLAY = False
OVERLAY_KEY  = 'f9'

SOUND_ON     = (1000, 80)
SOUND_OFF    = (400,  80)

# Exact Valorant enemy purple — slightly wider to catch all lighting
PURPLE_LOWER = np.array([128,  60,  70], dtype=np.uint8)
PURPLE_UPPER = np.array([174, 255, 255], dtype=np.uint8)

MIN_AREA  = 15
MERGE_GAP = 12      # sirf same enemy ke tukde merge hon, alag enemies alag rahein
LOCK_RADIUS = 16
LOCK_PIXELS = 4

try:
    cv2.setNumThreads(1)
except Exception:
    pass

# ──────────────────────────────────────────────
# STATE
# ──────────────────────────────────────────────
_boxes   = []
_locked  = False
_enabled = True
_overlay_enabled = SHOW_OVERLAY
_held    = False
_lock    = threading.Lock()
_quit    = threading.Event()


def _press():
    global _held
    if not _held:
        keyboard.press(KEY)
        _held = True

def _release():
    global _held
    if _held:
        keyboard.release(KEY)
        _held = False

def _beep(f, d):
    threading.Thread(target=winsound.Beep, args=(f,d), daemon=True).start()

def _toggle(_):
    global _enabled
    _enabled = not _enabled
    if _enabled:
        _beep(*SOUND_ON);  print("[ON]")
    else:
        _release(); _beep(*SOUND_OFF); print("[OFF]")

def _toggle_overlay(_):
    global _overlay_enabled
    _overlay_enabled = not _overlay_enabled
    print(f"[Overlay] {'ON' if _overlay_enabled else 'OFF'}")

keyboard.on_press_key(TOGGLE_KEY, _toggle)
keyboard.on_press_key(OVERLAY_KEY, _toggle_overlay)
keyboard.on_press_key(QUIT_KEY,   lambda _: _quit.set())

# ──────────────────────────────────────────────
# MERGE BOXES
# ──────────────────────────────────────────────
def merge_boxes(boxes, gap=8):
    if not boxes:
        return []
    boxes = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        result  = []
        used    = [False]*len(boxes)
        for i in range(len(boxes)):
            if used[i]: continue
            x1,y1,w1,h1 = boxes[i]
            ex1,ey1 = x1+w1, y1+h1
            for j in range(i+1,len(boxes)):
                if used[j]: continue
                x2,y2,w2,h2 = boxes[j]
                ex2,ey2 = x2+w2,y2+h2
                if x2-gap<ex1 and ex2+gap>x1 and y2-gap<ey1 and ey2+gap>y1:
                    boxes[i] = [min(x1,x2),min(y1,y2),
                                 max(ex1,ex2)-min(x1,x2),
                                 max(ey1,ey2)-min(y1,y2)]
                    x1,y1,w1,h1 = boxes[i]
                    ex1,ey1 = x1+w1,y1+h1
                    used[j] = True
                    changed = True
            result.append(list(boxes[i]))
        boxes = result
    return [tuple(b) for b in boxes]

# ──────────────────────────────────────────────
# DETECTION THREAD
# ──────────────────────────────────────────────
def detection_loop(sw, sh, cx, cy):
    global _boxes, _locked

    sct   = mss.mss()
    mon   = sct.monitors[1]
    delay = 1.0 / FPS

    # Only capture the crosshair/FOV area. Full-screen grabs are the main FPS killer.
    cap_x = max(0, cx - DETECTION_FOV)
    cap_y = max(0, cy - DETECTION_FOV)
    cap_w = min(sw, cx + DETECTION_FOV) - cap_x
    cap_h = min(sh, cy + DETECTION_FOV) - cap_y

    region = {
        "top":    mon["top"]  + cap_y,
        "left":   mon["left"] + cap_x,
        "width":  cap_w,
        "height": cap_h,
    }

    # Scaled crosshair position
    scx = int((cx - cap_x) * SCALE)
    scy = int((cy - cap_y) * SCALE)
    small_size = (max(1, int(cap_w * SCALE)), max(1, int(cap_h * SCALE)))
    dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))

    while not _quit.is_set():
        t0 = time.perf_counter()

        if _enabled:
            # Grab
            raw   = sct.grab(region)
            frame = np.asarray(raw)

            # SCALE DOWN — biggest CPU saver
            small_bgra = cv2.resize(frame,
                                    small_size,
                                    interpolation=cv2.INTER_NEAREST)  # fastest interp

            # Color detect: HSV range plus magenta dominance for the bright purple glow.
            small_bgr = small_bgra[:, :, :3]
            hsv  = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2HSV)
            hsv_mask = cv2.inRange(hsv, PURPLE_LOWER, PURPLE_UPPER)

            b = small_bgr[:, :, 0].astype(np.int16)
            g = small_bgr[:, :, 1].astype(np.int16)
            r = small_bgr[:, :, 2].astype(np.int16)
            purple_bias = (
                (r > 105) & (b > 105) &
                (r > g + 20) & (b > g + 10)
            )
            mask = cv2.bitwise_and(hsv_mask, (purple_bias.astype(np.uint8) * 255))

            # Dilate to connect same-enemy outline pieces only
            mask = cv2.dilate(mask, dilate_kernel, iterations=2)

            hit_r = max(2, int(LOCK_RADIUS * SCALE))
            x1 = max(0, scx - hit_r)
            x2 = min(mask.shape[1], scx + hit_r + 1)
            y1 = max(0, scy - hit_r)
            y2 = min(mask.shape[0], scy + hit_r + 1)
            locked = np.count_nonzero(mask[y1:y2, x1:x2]) >= LOCK_PIXELS

            boxes = []
            if _overlay_enabled:
                cnts,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                          cv2.CHAIN_APPROX_SIMPLE)
                raw_b = []
                for c in cnts:
                    if cv2.contourArea(c) < MIN_AREA:
                        continue
                    x,y,w,h = cv2.boundingRect(c)
                    asp = h / max(w,1)
                    if not (0.3 <= asp <= 6.0):  # tall body box allow
                        continue
                    # Scale back to full screen coords
                    fx = int(x/SCALE) + cap_x
                    fy = int(y/SCALE) + cap_y
                    fw = int(w/SCALE)
                    fh2= int(h/SCALE)
                    raw_b.append([fx,fy,fw,fh2])

                boxes = merge_boxes(raw_b, int(MERGE_GAP/SCALE))

            with _lock:
                _boxes  = boxes
                _locked = locked

            _press() if locked else _release()

        else:
            with _lock:
                _boxes  = []
                _locked = False
            _release()

        dt = time.perf_counter() - t0
        wait = delay - dt
        if wait > 0:
            time.sleep(wait)

# ──────────────────────────────────────────────
# TRANSPARENT OVERLAY
# ──────────────────────────────────────────────
WS_EX_TOPMOST    = 0x00000008
WS_EX_TRANSPARENT= 0x00000020
WS_EX_LAYERED    = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
GWL_EXSTYLE      = -20
LWA_COLORKEY     = 0x00000001

def make_overlay(sw, sh):
    name = "valo_bot_ov"
    cv2.namedWindow(name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    hwnd  = ctypes.windll.user32.FindWindowW(None, name)
    style = WS_EX_TOPMOST|WS_EX_TRANSPARENT|WS_EX_LAYERED|WS_EX_TOOLWINDOW
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    ctypes.windll.user32.SetLayeredWindowAttributes(hwnd,0,0,LWA_COLORKEY)
    HWND_TOPMOST = ctypes.c_void_p(-1)
    ctypes.windll.user32.SetWindowPos(hwnd,HWND_TOPMOST,0,0,sw,sh,
                                      0x0002|0x0001|0x0020)
    return name

# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    mon = mss.mss().monitors[1]
    sw  = mon["width"]
    sh  = mon["height"]
    cx  = sw//2
    cy  = sh//2

    # Set this process to low priority
    ctypes.windll.kernel32.SetPriorityClass(
        ctypes.windll.kernel32.GetCurrentProcess(),
        0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS

    threading.Thread(target=detection_loop,
                     args=(sw,sh,cx,cy), daemon=True).start()

    win   = None
    delay = 1 / OVERLAY_FPS

    _beep(*SOUND_ON)
    print("[*] Started | F10=toggle | F9=overlay | F7=quit")

    FOV = 250  # white FOV square half size
    canvas = np.zeros((sh, sw, 3), dtype=np.uint8)

    try:
        while not _quit.is_set():
            t0 = time.perf_counter()

            if not _overlay_enabled:
                if win is not None:
                    cv2.destroyWindow(win)
                    win = None
                time.sleep(0.05)
                continue

            if win is None:
                win = make_overlay(sw, sh)

            canvas.fill(0)

            with _lock:
                enabled = _enabled
                boxes   = list(_boxes)
                locked  = _locked

            if enabled:
                # FOV white square
                cv2.rectangle(canvas,
                              (cx-FOV, cy-FOV),
                              (cx+FOV, cy+FOV),
                              (255,255,255), 1)

                for (x,y,w,h) in boxes:
                    col = (30,30,255) if locked else (255,255,255)
                    # Simple corner box
                    cl = max(min(w,h)//4, 4)
                    cv2.rectangle(canvas,(x,y),(x+w,y+h),col,1)
                    for (ax,ay),(bx,by),(ex,ey) in [
                        ((x,y),(x+cl,y),(x,y+cl)),
                        ((x+w,y),(x+w-cl,y),(x+w,y+cl)),
                        ((x,y+h),(x+cl,y+h),(x,y+h-cl)),
                        ((x+w,y+h),(x+w-cl,y+h),(x+w,y+h-cl)),
                    ]:
                        cv2.line(canvas,(ax,ay),(bx,by),col,2)
                        cv2.line(canvas,(ax,ay),(ex,ey),col,2)

                    # Head zone
                    cv2.rectangle(canvas,(x,y),(x+w,y+max(int(h*0.25),3)),
                                  (0,200,255),1)

                # Crosshair
                dc = (30,30,255) if locked else (130,130,130)
                cv2.line(canvas,(cx-10,cy),(cx+10,cy),dc,1)
                cv2.line(canvas,(cx,cy-10),(cx,cy+10),dc,1)

            else:
                cv2.putText(canvas,"OFF",(cx-15,cy),
                            cv2.FONT_HERSHEY_SIMPLEX,0.6,(60,60,180),2)

            cv2.imshow(win, canvas)
            if cv2.waitKey(1) & 0xFF == 27:
                break

            dt = time.perf_counter() - t0
            w2 = delay - dt
            if w2 > 0:
                time.sleep(w2)

    finally:
        _release()
        keyboard.unhook_all()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
