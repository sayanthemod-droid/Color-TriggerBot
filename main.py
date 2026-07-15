"""
VALORANT ULTIMATE OVERLAY SUITE
================================
F1  = Toggle Trigger Bot (purple detection + K press on head)
F2  = Toggle Recoil Recorder (record spray pattern)
F3  = Toggle Sound Radar (directional audio overlay)
F4  = Toggle Clip Saver (auto highlight recording)
F9  = Toggle Visual Overlay (hide/show)
F10 = Toggle ALL overlays ON/OFF
F7  = Quit everything
"""

import threading
import keyboard
import winsound
import time
import mss

from modules.overlay    import OverlayWindow
from modules.trigger    import TriggerBot
from modules.recoil     import RecoilRecorder
from modules.sound_radar import SoundRadar
from modules.clip_saver import ClipSaver

OVERLAY_FPS = 30

# ── Screen info ──────────────────────────────
sct     = mss.mss()
monitor = sct.monitors[1]
SW      = monitor["width"]
SH      = monitor["height"]
CX      = SW // 2
CY      = SH // 2

# ── Shared quit event ────────────────────────
quit_event = threading.Event()

def beep(f, d):
    threading.Thread(target=winsound.Beep, args=(f, d), daemon=True).start()

def main():
    print("=" * 60)
    print("  VALORANT SUITE  |  Starting...")
    print("=" * 60)
    print()
    print("  ✓ Detection: Purple enemy outline scanning")
    print("  ✓ Key Press: Auto 'K' when on head")
    print()
    print("=" * 60)

    # Create shared overlay window
    overlay = OverlayWindow(SW, SH)

    # Init modules
    trigger  = TriggerBot(SW, SH, CX, CY, overlay)
    recoil   = RecoilRecorder(SW, SH, CX, CY, overlay)
    radar    = SoundRadar(SW, SH, CX, CY, overlay)
    clipper  = ClipSaver(SW, SH, monitor)

    modules = [trigger, recoil, radar, clipper]

    # Start all background threads
    for m in modules:
        m.start()

    # Key bindings
    def toggle_all(_):
        enabled = not all(m.enabled for m in modules)
        for m in modules:
            m.enabled = enabled
        beep(1000 if enabled else 400, 100)
        print(f"[*] ALL {'ON' if enabled else 'OFF'}")

    keyboard.on_press_key("f1",  lambda _: trigger.toggle())
    keyboard.on_press_key("f2",  lambda _: recoil.toggle())
    keyboard.on_press_key("f3",  lambda _: radar.toggle())
    keyboard.on_press_key("f4",  lambda _: clipper.toggle())
    keyboard.on_press_key("f9",  lambda _: trigger.toggle_visual())  # Toggle visual overlay
    keyboard.on_press_key("f10", toggle_all)
    keyboard.on_press_key("f7",  lambda _: quit_event.set())

    beep(1000, 120)
    print()
    print("=" * 60)
    print("  🎯 READY")
    print("=" * 60)
    print()
    print("  HOTKEYS:")
    print("    F1  = Toggle Trigger Bot (purple detection + K press)")
    print("    F2  = Toggle Recoil Recorder")
    print("    F3  = Toggle Sound Radar")
    print("    F4  = Toggle Clip Saver")
    print("    F9  = Toggle Visual Overlay (hide/show)")
    print("    F10 = Toggle ALL modules")
    print("    F7  = Quit")
    print()
    print("  TRIGGER INFO:")
    print("    • Detects purple enemy outlines")
    print("    • Auto presses 'K' when aiming at head")
    print("    • Green line shows nearest target")
    print()
    print("=" * 60)
    print()

    # Main overlay draw loop
    try:
        while not quit_event.is_set():
            overlay.render(trigger, recoil, radar, clipper, CX, CY)
            time.sleep(1 / OVERLAY_FPS)
    finally:
        for m in modules:
            m.stop()
        keyboard.unhook_all()
        overlay.close()
        print("[*] Stopped.")

if __name__ == "__main__":
    main()
