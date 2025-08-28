# raw_mouse_macro.py
# Records raw mouse deltas via WM_INPUT and replays them as relative moves.
# Hotkeys: F9 = start/stop recording, F10 = play, F12 = stop playback

from win_setup import *
import os
import pickle
import ctypes
from ctypes import wintypes
import threading
import time
import sys
from pynput import keyboard

# -------- Macro paths --------
MACRO_DIR = "macros"
MACROS_FILE = "MACRO_VARS.txt"
os.makedirs(MACRO_DIR, exist_ok=True)

# Define which macros to cycle through for playback
MACROS_TO_PLAY = ["macro_002.pkl"]
current_macro_index = 0

# -------- Recorder state --------
recording = []
is_recording = False
is_playing = False
stop_playback = False
t0 = 0.0

# Globals to prevent GC
_lpfnWndProc_ref = None
_hook_ref = None


# -------- Window proc (raw mouse only) --------
def wndproc(hwnd, msg, wParam, lParam):
    global is_recording, t0, recording
    if msg == WM_INPUT:
        size = wintypes.UINT(0)
        user32.GetRawInputData(
            lParam, RID_INPUT, None,
            ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER)
        )
        if size.value:
            buf = ctypes.create_string_buffer(size.value)
            got = user32.GetRawInputData(
                lParam, RID_INPUT, buf,
                ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER)
            )
            if got == size.value:
                ri = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents
                if ri.header.dwType == 0:  # RIM_TYPEMOUSE
                    dx = ri.data.mouse.lLastX
                    dy = ri.data.mouse.lLastY
                    btns = ri.data.mouse.ulButtons
                    if is_recording:
                        t = time.perf_counter() - t0
                        if dx != 0 or dy != 0:
                            recording.append(("move", int(dx), int(dy), t))
                        if btns != 0:
                            recording.append(("button", int(btns), 0, t))
        return 0
    return user32.DefWindowProcW(hwnd, msg, wParam, lParam)

# -------- Message loop --------
def message_loop():
    msg = wintypes.MSG()
    while True:
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == 0:
            break
        elif ret == -1:
            raise ctypes.WinError()
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

# -------- Macro loading --------
def load_macros():
    if not os.path.exists(MACROS_FILE):
        print(f"Macros file {MACROS_FILE} not found!")
        return []
    with open(MACROS_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    print(f"Loaded macros from {MACROS_FILE}: {lines}")
    return lines

# -------- Playback primitives --------
def send_key_event(keycode, down=True):
    inp = INPUT()
    inp.type = 1
    flags = 0 if down else 0x0002
    inp.union.ki = KEYBDINPUT(
        wVk=keycode, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

def send_relative_move(dx, dy):
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi = MOUSEINPUT(
        dx=dx, dy=dy, mouseData=0,
        dwFlags=MOUSEEVENTF_MOVE, time=0, dwExtraInfo=0
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

def send_mouse_button(btn, down=True):
    flags = 0
    if btn == "left":
        flags = 0x0002 if down else 0x0004
    elif btn == "right":
        flags = 0x0008 if down else 0x0010
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi = MOUSEINPUT(0, 0, 0, flags, 0, 0)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

# -------- Macro playback --------
def play_macro():
    global is_playing, stop_playback, current_macro_index
    is_playing = True
    stop_playback = False
    current_macro_index = 0
    while not stop_playback:
        macros_to_play = load_macros()
        if not macros_to_play:
            print(f"No macros defined in {MACROS_FILE}. Stopping playback.")
            break
        macro_name = macros_to_play[current_macro_index]
        path = os.path.join(MACRO_DIR, macro_name)
        if not os.path.exists(path):
            print(f"Macro {macro_name} not found in {MACRO_DIR}. Skipping.")
            current_macro_index = (current_macro_index + 1) % len(macros_to_play)
            continue
        with open(path, "rb") as f:
            events = pickle.load(f)
        print(f"Playing {macro_name} ({len(events)} events) ... (F12 to stop)")
        start_play = time.perf_counter()
        for etype, dx, dy, t in events:
            if stop_playback:
                break
            target = start_play + (t / PLAYBACK_SPEED)
            while time.perf_counter() < target and not stop_playback:
                time.sleep(0.0005)
            if etype == "move":
                send_relative_move(dx, dy)
            elif etype == "button":
                btns = dx
                if btns & 0x0001: send_mouse_button("left", True)
                if btns & 0x0002: send_mouse_button("left", False)
                if btns & 0x0004: send_mouse_button("right", True)
                if btns & 0x0008: send_mouse_button("right", False)
            elif etype == "key":
                send_key_event(dx, bool(dy))
        print(f"Finished {macro_name}")
        current_macro_index = (current_macro_index + 1) % len(macros_to_play)
        time.sleep(0.1)
    print("Playback stopped.")
    is_playing = False

# -------- Hotkey logic --------
def save_new_macro(events):
    i = 1
    while True:
        name = f"macro_{i:03d}.pkl"
        path = os.path.join(MACRO_DIR, name)
        if not os.path.exists(path):
            break
        i += 1
    with open(path, "wb") as f:
        pickle.dump(events, f)
    print(f"Saved macro to {path}")

def handle_hotkey(vkCode):
    global is_recording, t0, recording, stop_playback
    if vkCode == VK_F9:
        if not is_recording:
            print("Recording started... (F9 to stop)")
            recording.clear()
            is_recording = True
            t0 = time.perf_counter()
        else:
            is_recording = False
            print(f"Recording stopped. Events: {len(recording)}")
            threading.Thread(target=save_new_macro, args=(recording,), daemon=True).start()
    elif vkCode == VK_F10:
        if not is_playing:
            threading.Thread(target=play_macro, daemon=True).start()
    elif vkCode == VK_F12:
        if is_playing:
            print("Stopping playback...")
            stop_playback = True

# -------- Low-level keyboard hook --------
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100

LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    wintypes.LRESULT, wintypes.INT, wintypes.WPARAM, wintypes.LPARAM
)

def hook_proc(nCode, wParam, lParam):
    try:
        if nCode == 0 and wParam == WM_KEYDOWN:
            vkCode = ctypes.cast(lParam, ctypes.POINTER(ctypes.c_int))[0]
            if vkCode in (VK_F9, VK_F10, VK_F12):
                handle_hotkey(vkCode)
    except KeyboardInterrupt:
        return 0
    return user32.CallNextHookEx(None, nCode, wParam, lParam)

# -------- Recording other keys (pynput) --------
def record_press(key):
    try:
        vk = key.vk if hasattr(key, "vk") else key.value.vk
    except AttributeError:
        vk = 0
    t = time.perf_counter() - t0
    if is_recording and key not in {keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f12}:
        recording.append(("key", int(vk), 1, t))

def record_release(key):
    try:
        vk = key.vk if hasattr(key, "vk") else key.value.vk
    except AttributeError:
        vk = 0
    t = time.perf_counter() - t0
    if is_recording and key not in {keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f12}:
        recording.append(("key", int(vk), 0, t))

# -------- Main --------
def main():
    global _lpfnWndProc_ref, _hook_ref, stop_playback

    # Setup hidden window
    class_name = "RawMouseRecorderWindow"
    _lpfnWndProc_ref = make_wndclass(class_name, wndproc)
    hwnd = create_window(class_name, "raw_mouse_hidden")

    # Register raw mouse input
    rid = RAWINPUTDEVICE(
        usUsagePage=HID_USAGE_PAGE_GENERIC,
        usUsage=HID_USAGE_GENERIC_MOUSE,
        dwFlags=RIDEV_INPUTSINK,
        hwndTarget=hwnd
    )
    if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)):
        raise ctypes.WinError()

    print("Raw mouse macro ready.")
    print("F9 = start/stop record, F10 = play, F12 = stop playback.")

    # Start key recorder for normal keys
    kl = keyboard.Listener(on_press=record_press, on_release=record_release)
    kl.start()

    # Install global low-level keyboard hook
    HOOKPROC = LowLevelKeyboardProc(hook_proc)
    _hook_ref = HOOKPROC
    hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, HOOKPROC, 0, 0)
    if not hook:
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        message_loop()
    except KeyboardInterrupt:
        pass
    finally:
        user32.UnhookWindowsHookEx(hook)
        stop_playback = True
        kl.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
