# win_setup.py
import ctypes
from ctypes import wintypes
import os
import time
import pickle
import queue

# ---------------------------
# Pointer-size types (64/32-bit)
# ---------------------------
if ctypes.sizeof(ctypes.c_void_p) == 8:  # 64-bit
    wintypes.LRESULT = ctypes.c_int64
    wintypes.WPARAM  = ctypes.c_uint64
    wintypes.LPARAM  = ctypes.c_int64
    ULONG_PTR = ctypes.c_ulonglong
else:  # 32-bit
    wintypes.LRESULT = ctypes.c_long
    wintypes.WPARAM  = ctypes.c_uint
    wintypes.LPARAM  = ctypes.c_long
    ULONG_PTR = ctypes.c_ulong

wintypes.HCURSOR = wintypes.HANDLE
wintypes.HICON   = wintypes.HANDLE

# ---------------------------
# Win32 constants
# ---------------------------
WM_INPUT        = 0x00FF
WM_KEYDOWN      = 0x0100
WM_KEYUP        = 0x0101
WM_SYSKEYDOWN   = 0x0104
WM_SYSKEYUP     = 0x0105

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100

RID_INPUT       = 0x10000003
RIDEV_INPUTSINK = 0x00000100

HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_GENERIC_MOUSE = 0x02

INPUT_MOUSE     = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_MOVE_NOCOALESCE = 0x2000

# Virtual key codes
VK_F9  = 0x78
VK_F10 = 0x79
VK_F12 = 0x7B
WM_INPUT = 0x00FF

# Playback tuning
PLAYBACK_SPEED = 1.0
MIN_DELAY = 0.001
CHUNK_MS = 8

# Thread priority / timing
HIGH_PRIORITY_CLASS = 0x00000080
THREAD_PRIORITY_TIME_CRITICAL = 15

# Mouse settings
SPI_GETMOUSE = 0x0003
SPI_SETMOUSE = 0x0004
MOUSEEVENTF_MOVE_NOCOALESCE = 0x2000

# ---------------------------
# Win32 handles
# ---------------------------
user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
winmm    = ctypes.WinDLL('winmm')

# DefWindowProcW prototype
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype  = wintypes.LRESULT

# ---------------------------
# RAWINPUT structs
# ---------------------------
class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]

class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("ulButtons", wintypes.ULONG),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", ctypes.c_long),
        ("lLastY", ctypes.c_long),
        ("ulExtraInformation", wintypes.ULONG),
    ]

class RAWINPUTUNION(ctypes.Union):
    _fields_ = [("mouse", RAWMOUSE)]

class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", RAWINPUTUNION),
    ]

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]

# ---------------------------
# SendInput structs
# ---------------------------
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUTUNION),
    ]

# ---------------------------
# Low-level keyboard struct
# ---------------------------
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

# ---------------------------
# Function prototypes
# ---------------------------
user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT]
user32.RegisterRawInputDevices.restype  = wintypes.BOOL

user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT), wintypes.UINT]
user32.GetRawInputData.restype = wintypes.UINT

user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

# ---------------------------
# Window + WndProc helpers
# ---------------------------
WNDPROCTYPE = ctypes.WINFUNCTYPE(wintypes.LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

def make_wndclass(name, wndproc):
    class WNDCLASS(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROCTYPE),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HCURSOR),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]
    wc = WNDCLASS()
    wc.style = 0
    wc.lpfnWndProc = WNDPROCTYPE(wndproc)
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.hIcon = None
    wc.hCursor = None
    wc.hbrBackground = None
    wc.lpszMenuName = None
    wc.lpszClassName = name
    atom = user32.RegisterClassW(ctypes.byref(wc))
    if not atom:
        raise ctypes.WinError()
    return wc.lpfnWndProc  # keep reference to prevent GC

def create_window(class_name, title):
    hwnd = user32.CreateWindowExW(
        0, class_name, title,
        0, 0, 0, 0, 0,
        None, None, kernel32.GetModuleHandleW(None), None
    )
    if not hwnd:
        raise ctypes.WinError()
    return hwnd

# ---------------------------
# Low-level keyboard hook prototype
# ---------------------------
LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    wintypes.LRESULT, wintypes.INT, wintypes.WPARAM, wintypes.LPARAM
)
