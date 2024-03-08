#!/usr/bin/env python
"""
ALT-Scann8 UI - Alternative software for T-Scann 8

This tool is a fork of the original user interface application of T-Scann 8

Some additional features of this version include:
- PiCamera 2 integration
- Use of Tkinter instead of Pygame
- Automatic exposure support
- Fast forward support

Licensed under a MIT LICENSE.

More info in README.md file
"""

__author__ = 'Juan Remirez de Esparza'
__copyright__ = "Copyright 2022-24, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__module__ = "ALT-Scann8"
__version__ = "1.10.18"
__date__ = "2024-03-08"
__version_highlight__ = "Reformat code - Cut lines longer than 120 chars"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"

# ######### Imports section ##########
import tkinter as tk
from tkinter import filedialog

import tkinter.messagebox
import tkinter.simpledialog
from tkinter import DISABLED, NORMAL, LEFT, RIGHT, Y, TOP, BOTTOM, N, W, E, NW, RAISED, SUNKEN
from tkinter import Label, Button, Frame, LabelFrame, Canvas, OptionMenu

from PIL import ImageTk, Image

import os
import time
import json

from datetime import datetime
import logging
import sys
import getopt

import numpy as np

try:
    import psutil

    check_disk_space = True
except ImportError:
    check_disk_space = False

try:
    import smbus
    from picamera2 import Picamera2, Preview
    from libcamera import Transform
    from libcamera import controls

    # Global variable to isolate camera specific code (Picamera vs PiCamera2)
    IsPiCamera2 = True
    # Global variable to allow basic UI testing on PC (where PiCamera imports should fail)
    SimulatedRun = False
except ImportError:
    SimulatedRun = True

import threading
import queue
import cv2
import re

from camera_resolutions import CameraResolutions
from dynamic_spinbox import DynamicSpinbox
from tooltip import Tooltips
from rolling_average import RollingAverage

#  ######### Global variable definition (I know, too many...) ##########
win = None
as_tooltips = None
ExitingApp = False
add_vertical_scrollbar = False
Controller_Id = 0  # 1 - Arduino, 2 - RPi Pico
FocusState = True
lastFocus = True
FocusZoomActive = False
FocusZoomPosX = 0.35
FocusZoomPosY = 0.35
FocusZoomFactorX = 0.2
FocusZoomFactorY = 0.2
FreeWheelActive = False
BaseDir = '/home/juan/Vídeos'  # dirplats in original code from Torulf
CurrentDir = BaseDir
FrameFilenamePattern = "picture-%05d.%s"
HdrFrameFilenamePattern = "picture-%05d.%1d.%s"  # HDR frames using standard filename (2/12/2023)
StillFrameFilenamePattern = "still-picture-%05d-%02d.jpg"
CurrentFrame = 0  # bild in original code from Torulf
frames_to_go_key_press_time = 0
CurrentStill = 1  # used to take several stills of same frame, for settings analysis
CurrentScanStartTime = datetime.now()
CurrentScanStartFrame = 0
HdrCaptureActive = False
AdvanceMovieActive = False
RetreatMovieActive = False
RewindMovieActive = False  # SpolaState in original code from Torulf
RewindErrorOutstanding = False
RewindEndOutstanding = False
rwnd_speed_delay = 200  # informational only, should be in sync with Arduino, but for now we do not secure it
FastForwardActive = False
FastForwardErrorOutstanding = False
FastForwardEndOutstanding = False
ScanOngoing = False  # PlayState in original code from Torulf (opposite meaning)
ScanStopRequested = False  # To handle stopping scan process asynchronously, with same button as start scan
NewFrameAvailable = False  # To be set to true upon reception of Arduino event
ScanProcessError = False  # To be set to true upon reception of Arduino event
ScanProcessError_LastTime = 0
# Directory where python scrips run, to store the json file with persistent data
ScriptDir = os.path.dirname(__file__)
PersistedDataFilename = os.path.join(ScriptDir, "ALT-Scann8.json")
PersistedDataLoaded = False
# Variables to deal with remaining disk space
available_space_mb = 0
disk_space_error_to_notify = False

ArduinoTrigger = 0
last_frame_time = 0
reference_inactivity_delay = 6  # Max time (in sec) we wait for next frame. If expired, we force next frame again
max_inactivity_delay = reference_inactivity_delay
# Minimum number of steps per frame, to be passed to Arduino
MinFrameStepsS8 = 290
MinFrameStepsR8 = 240
# Phototransistor reported level when hole is detected
PTLevelS8 = 80
PTLevelR8 = 120
# Tokens identify type of elements in queues
# Token to be inserted in each queue on program closure, to allow threads to shut down cleanly
active_threads = 0
num_threads = 0
END_TOKEN = "TERMINATE_PROCESS"  # Sent on program closure, to allow threads to shut down cleanly
IMAGE_TOKEN = "IMAGE_TOKEN"  # Queue element is an image
REQUEST_TOKEN = "REQUEST_TOKEN"  # Queue element is a PiCamera2 request
MaxQueueSize = 16
DisableThreads = False
FrameArrivalTime = 0
# Ids to allow cancelling afters on exit
onesec_after = 0
arduino_after = 0
# Variables to track windows movement and set preview accordingly
TopWinX = 0
TopWinY = 0
PreviewWinX = 90
PreviewWinY = 75
PreviewWidth = 0
PreviewHeight = 0
FilmHoleY_Top = 0
FilmHoleY_Bottom = 0
FilmHoleHeightTop = 0
FilmHoleHeightBottom = 0
DeltaX = 0
DeltaY = 0
WinInitDone = False
FontSize = 0
FolderProcess = 0
LoggingMode = "INFO"
LogLevel = 0
draw_capture_canvas = 0
button_lock_counter = 0

PiCam2PreviewEnabled = False
PostviewCounter = 0
FramesPerMinute = 0
FramesToGo = 0
RPiTemp = 0
last_temp = 1  # Needs to be different from RPiTemp the first time
LastTempInFahrenheit = False
save_bg = 'gray'
save_fg = 'black'
ZoomSize = 0
simulated_captured_frame_list = [None] * 1000
simulated_capture_image = ''
simulated_images_in_list = 0

# Commands (RPI to Arduino)
CMD_VERSION_ID = 1
CMD_GET_CNT_STATUS = 2
CMD_RESET_CONTROLLER = 3
CMD_START_SCAN = 10
CMD_TERMINATE = 11
CMD_GET_NEXT_FRAME = 12
CMD_STOP_SCAN = 13
CMD_SET_REGULAR_8 = 18
CMD_SET_SUPER_8 = 19
CMD_SWITCH_REEL_LOCK_STATUS = 20
CMD_FILM_FORWARD = 30
CMD_FILM_BACKWARD = 31
CMD_SINGLE_STEP = 40
CMD_ADVANCE_FRAME = 41
CMD_ADVANCE_FRAME_FRACTION = 42
CMD_SET_PT_LEVEL = 50
CMD_SET_MIN_FRAME_STEPS = 52
CMD_SET_FRAME_FINE_TUNE = 54
CMD_SET_EXTRA_STEPS = 56
CMD_REWIND = 60
CMD_FAST_FORWARD = 61
CMD_INCREASE_WIND_SPEED = 62
CMD_DECREASE_WIND_SPEED = 63
CMD_UNCONDITIONAL_REWIND = 64
CMD_UNCONDITIONAL_FAST_FORWARD = 65
CMD_SET_SCAN_SPEED = 70
CMD_SET_STALL_TIME = 72
CMD_SET_AUTO_STOP = 74
CMD_REPORT_PLOTTER_INFO = 87
# Responses (Arduino to RPi)
RSP_VERSION_ID = 1
RSP_FORCE_INIT = 2
RSP_FRAME_AVAILABLE = 80
RSP_SCAN_ERROR = 81
RSP_REWIND_ERROR = 82
RSP_FAST_FORWARD_ERROR = 83
RSP_REWIND_ENDED = 84
RSP_FAST_FORWARD_ENDED = 85
RSP_REPORT_AUTO_LEVELS = 86
RSP_REPORT_PLOTTER_INFO = 87
RSP_SCAN_ENDED = 88
RSP_FILM_FORWARD_ENDED = 89

# Expert mode variables - By default Exposure and white balance are set as automatic, with adapt delay
ExpertMode = True
ExperimentalMode = True
PlotterMode = True
keep_control_widgets_enabled = True
plotter_canvas = None
plotter_width = 20
plotter_height = 10
PrevPTValue = 0
PrevThresholdLevel = 0
MaxPT = 100
MinPT = 800
Tolerance_AE = 8000
Tolerance_AWB = 1
manual_wb_red_value = 2.2
manual_wb_blue_value = 2.2
PreviousCurrentExposure = 0  # Used to spot changes in exposure, and cause a delay to allow camera to adapt
PreviousGainRed = 1
PreviousGainBlue = 1
ManualScanEnabled = False
CameraDisabled = False  # To allow testing scanner without a camera installed

# Dictionaries for additional exposure control with PiCamera2
if not SimulatedRun and not CameraDisabled:
    AeConstraintMode_dict = {
        "Normal": controls.AeConstraintModeEnum.Normal,
        "Highlight": controls.AeConstraintModeEnum.Highlight,
        "Shadows": controls.AeConstraintModeEnum.Shadows
    }
    AeMeteringMode_dict = {
        "CentreWeighted": controls.AeMeteringModeEnum.CentreWeighted,
        "Spot": controls.AeMeteringModeEnum.Spot,
        "Matrix": controls.AeMeteringModeEnum.Matrix
    }
    AeExposureMode_dict = {
        "Normal": controls.AeExposureModeEnum.Normal,
        "Long": controls.AeExposureModeEnum.Long,
        "Short": controls.AeExposureModeEnum.Short
    }
    AwbMode_dict = {
        "Auto": controls.AwbModeEnum.Auto,
        "Tungsten": controls.AwbModeEnum.Tungsten,
        "Fluorescent": controls.AwbModeEnum.Fluorescent,
        "Indoor": controls.AwbModeEnum.Indoor,
        "Daylight": controls.AwbModeEnum.Daylight,
        "Cloudy": controls.AwbModeEnum.Cloudy
    }
else:
    AeConstraintMode_dict = {
        "Normal": 1,
        "Highlight": 2,
        "Shadows": 3
    }
    AeMeteringMode_dict = {
        "CentreWeighted": 1,
        "Spot": 2,
        "Matrix": 3
    }
    AeExposureMode_dict = {
        "Normal": 1,
        "Long": 2,
        "Short": 3
    }
    AwbMode_dict = {
        "Auto": 1,
        "Tungsten": 2,
        "Fluorescent": 3,
        "Indoor": 4,
        "Daylight": 5,
        "Cloudy": 6
    }

# Statistical information about where time is spent (expert mode only)
total_wait_time_save_image = 0
total_wait_time_preview_display = 0
total_wait_time_awb = 0
total_wait_time_autoexp = 0
time_save_image = None
time_preview_display = None
time_awb = None
time_autoexp = None
session_start_time = 0
session_frames = 0
max_wait_time = 5000
last_click_time = 0

ALT_Scann8_controller_detected = False

FPM_LastMinuteFrameTimes = list()
FPM_StartTime = time.ctime()
FPM_CalculatedValue = -1

# *** HDR variables
MergeMertens = None
images_to_merge = []
# 4 iterations seem to be enough for exposure to catch up (started with 9, 4 gives same results, 3 is not enough)
dry_run_iterations = 4
# HDR, min/max exposure range. Used to be from 10 to 150, but original values found elsewhere (1-56) are better
# Finally set to 4-104
hdr_lower_exp = 8
hdr_higher_exp = 104
hdr_best_exp = 0
hdr_min_bracket_width = 4
hdr_max_bracket_width = 400
hdr_num_exposures = 3  # Changed from 4 exposures to 3, probably an odd number is better (and 3 faster than 4)
hdr_step_value = 1
hdr_exp_list = []
hdr_rev_exp_list = []
HdrViewX4Active = False
recalculate_hdr_exp_list = False
force_adjust_hdr_bracket = False
hdr_auto_bracket_frames = 8  # Every n frames, bracket is recalculated

# *** Simulated sensor modes to ellaborate resolution list
camera_resolutions = None
simulated_sensor_modes = [{'bit_depth': 10,
                           'crop_limits': (696, 528, 2664, 1980),
                           'exposure_limits': (31, 667234896, None),
                           'format': 'SRGGB10_CSI2P',
                           'fps': 120.05,
                           'size': (1332, 990),
                           'unpacked': 'SRGGB10'},
                          {'bit_depth': 12,
                           'crop_limits': (0, 440, 4056, 2160),
                           'exposure_limits': (60, 674181621, None),
                           'format': 'SRGGB12_CSI2P',
                           'fps': 50.03,
                           'size': (2028, 1080),
                           'unpacked': 'SRGGB12'},
                          {'bit_depth': 12,
                           'crop_limits': (0, 0, 4056, 3040),
                           'exposure_limits': (60, 674181621, None),
                           'format': 'SRGGB12_CSI2P',
                           'fps': 40.01,
                           'size': (2028, 1520),
                           'unpacked': 'SRGGB12'},
                          {'bit_depth': 12,
                           'crop_limits': (0, 0, 4056, 3040),
                           'exposure_limits': (114, 694422939, None),
                           'format': 'SRGGB12_CSI2P',
                           'fps': 10.0,
                           'size': (4056, 3040),
                           'unpacked': 'SRGGB12'}]

# Persisted data
SessionData = {
    "CurrentDate": str(datetime.now()),
    "CurrentDir": CurrentDir,
    "CurrentFrame": str(CurrentFrame),
    "CurrentExposure": 0,
    "NegativeCaptureActive": False,
    "HdrCaptureActive": str(HdrCaptureActive),
    "FilmType": 'S8',
    "MinFrameStepsS8": 290,
    "MinFrameStepsR8": 240,
    "MinFrameSteps": 290,
    "FrameFineTune": 50,
    "FrameExtraSteps": 0,
    "PTLevelS8": 80,
    "PTLevelR8": 200,
    "PTLevel": 80,
    "PTLevelAuto": True,
    "FrameStepsAuto": True,
    "HdrMinExp": hdr_lower_exp,
    "HdrMaxExp": hdr_higher_exp,
    "HdrBracketWidth": 50,
    "HdrBracketShift": 0,
    "HdrBracketAuto": True,
    "HdrMergeInPlace": False,
    "FramesToGo": FramesToGo
}


# ********************************************************
# ALT-Scann8 code
# ********************************************************

def exit_app():  # Exit Application
    global ExitingApp

    win.config(cursor="watch")
    win.update()
    # Flag app is exiting for all outstanding afters to expire
    ExitingApp = True
    if onesec_after != 0:
        win.after_cancel(onesec_after)
    if arduino_after != 0:
        win.after_cancel(arduino_after)
    # Terminate threads
    if not SimulatedRun and not CameraDisabled:
        capture_display_event.set()
        capture_save_event.set()
        capture_display_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)

        while active_threads > 0:
            win.update()
            logging.debug(f"Waiting for threads to exit, {active_threads} pending")
            time.sleep(0.2)

    # Uncomment next two lines when running on RPi
    if not SimulatedRun:
        send_arduino_command(CMD_TERMINATE)  # Tell Arduino we stop (to turn off uv led
        # Close preview if required
        if not CameraDisabled:
            if PiCam2PreviewEnabled:
                camera.stop_preview()
            camera.close()
    # Set window position for next run
    SessionData["WindowPos"] = win.geometry()
    SessionData["AutoStopActive"] = auto_stop_enabled.get()
    SessionData["AutoStopType"] = autostop_type.get()
    if frames_to_go_str.get() == '':
        SessionData["FramesToGo"] = -1
    # Write session data upon exit
    with open(PersistedDataFilename, 'w') as f:
        json.dump(SessionData, f)

    win.config(cursor="")

    win.destroy()


def set_free_mode():
    global FreeWheelActive

    if not FreeWheelActive:
        Free_btn.config(text='Lock Reels', bg='red', fg='white', relief=SUNKEN)
    else:
        Free_btn.config(text='Unlock Reels', bg=save_bg, fg=save_fg, relief=RAISED)

    if not SimulatedRun:
        send_arduino_command(CMD_SWITCH_REEL_LOCK_STATUS)

    FreeWheelActive = not FreeWheelActive

    # Enable/Disable related buttons
    button_status_change_except(Free_btn, FreeWheelActive)


def set_auto_stop_enabled():
    if not SimulatedRun:
        send_arduino_command(CMD_SET_AUTO_STOP, auto_stop_enabled.get() and autostop_type.get() == 'No_film')
        logging.debug(f"Sent Auto Stop to Arduino: {auto_stop_enabled.get() and autostop_type.get() == 'No_film'}")
    autostop_no_film_rb.config(state=NORMAL if auto_stop_enabled.get() else DISABLED)
    autostop_counter_zero_rb.config(state=NORMAL if auto_stop_enabled.get() else DISABLED)
    logging.debug(f"Set Auto Stop: {auto_stop_enabled.get()}, {autostop_type.get()}")


# Enable/Disable camera zoom to facilitate focus
def set_focus_zoom():
    global FocusZoomActive

    if real_time_zoom.get():
        real_time_display_checkbox.config(state=DISABLED)
    else:
        real_time_display_checkbox.config(state=NORMAL)

    if not SimulatedRun and not CameraDisabled:
        if real_time_zoom.get():
            camera.set_controls(
                {"ScalerCrop": (int(FocusZoomPosX * ZoomSize[0]), int(FocusZoomPosY * ZoomSize[1])) +
                               (int(FocusZoomFactorX * ZoomSize[0]), int(FocusZoomFactorY * ZoomSize[1]))})
        else:
            camera.set_controls({"ScalerCrop": (0, 0) + (ZoomSize[0], ZoomSize[1])})

    time.sleep(.2)
    FocusZoomActive = not FocusZoomActive

    # Enable disable buttons for focus move
    focus_lf_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
    focus_up_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
    focus_dn_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
    focus_rt_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
    focus_plus_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
    focus_minus_btn.config(state=NORMAL if FocusZoomActive else DISABLED)


def adjust_focus_zoom():
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ScalerCrop": (int(FocusZoomPosX * ZoomSize[0]), int(FocusZoomPosY * ZoomSize[1])) +
                                           (int(FocusZoomFactorX * ZoomSize[0]), int(FocusZoomFactorY * ZoomSize[1]))})


def set_focus_up():
    global FocusZoomPosY
    if FocusZoomPosY >= 0.05:
        FocusZoomPosY = round(FocusZoomPosY - 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom up (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def set_focus_left():
    global FocusZoomPosX
    if FocusZoomPosX >= 0.05:
        FocusZoomPosX = round(FocusZoomPosX - 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom left (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def set_focus_right():
    global FocusZoomPosX
    if FocusZoomPosX <= (1 - (FocusZoomFactorX - 0.05)):
        FocusZoomPosX = round(FocusZoomPosX + 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom right (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def set_focus_down():
    global FocusZoomPosY
    if FocusZoomPosY <= (1 - (FocusZoomFactorY - 0.05)):
        FocusZoomPosY = round(FocusZoomPosY + 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom down (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def set_focus_plus():
    global FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY
    if FocusZoomFactorX >= 0.2:
        FocusZoomFactorX = round(FocusZoomFactorX - 0.1, 1)
        # Zoom factor is the same for X and Y, so we can safely add everything in the if statement for X
        if FocusZoomFactorY >= 0.2:
            FocusZoomFactorY = round(FocusZoomFactorY - 0.1, 1)
        # Adjust origin so that zoom is centered
        FocusZoomPosX = round(FocusZoomPosX + 0.05, 2)
        FocusZoomPosY = round(FocusZoomPosY + 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom plus (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def set_focus_minus():
    global FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY
    if FocusZoomFactorX < 0.9:
        FocusZoomFactorX = round(FocusZoomFactorX + 0.1, 1)
        # Zoom factor is the same for X and Y, so we can safely add everything in the if statement for X
        if FocusZoomFactorY < 0.9:
            FocusZoomFactorY = round(FocusZoomFactorY + 0.1, 1)
        # Adjust origin so that zoom is centered
        FocusZoomPosX = round(FocusZoomPosX - 0.05, 2)
        FocusZoomPosY = round(FocusZoomPosY - 0.05, 2)
        # Adjust boundaries if needed
        if FocusZoomPosX < 0:
            FocusZoomPosX = 0
        if FocusZoomPosY < 0:
            FocusZoomPosY = 0
        if FocusZoomPosX + FocusZoomFactorX > 1:
            FocusZoomPosX = round(1 - FocusZoomFactorX, 2)
        if FocusZoomPosY + FocusZoomFactorY > 1:
            FocusZoomPosY = round(1 - FocusZoomFactorY, 2)
        adjust_focus_zoom()
        logging.debug("Zoom plus (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def set_new_folder():
    global CurrentDir, CurrentFrame

    requested_dir = ""
    success = False

    while requested_dir == "" or requested_dir is None:
        requested_dir = tk.simpledialog.askstring(title="Enter new folder name",
                                                  prompt=f"Enter new folder name (to be created under {CurrentDir}):")
        if requested_dir is None:
            return
        if requested_dir == "":
            tk.messagebox.showerror("Error!", "Please specify a name for the folder to be created.")

    newly_created_dir = os.path.join(CurrentDir, requested_dir)

    if not os.path.isdir(newly_created_dir):
        try:
            os.mkdir(newly_created_dir)
            CurrentFrame = 0
            CurrentDir = newly_created_dir
            success = True
        except FileExistsError:
            tk.messagebox.showerror("Error", f"Folder {requested_dir} already exists.")
        except PermissionError:
            tk.messagebox.showerror("Error", f"Folder {requested_dir}, "
                                             "permission denied to create directory.")
        except OSError as e:
            tk.messagebox.showerror("Error", f"While creating folder {requested_dir}, OS error: {e}.")
        except Exception as e:
            tk.messagebox.showerror("Error", f"While creating folder {requested_dir}, "
                                             f"unexpected error: {e}.")
    else:
        tk.messagebox.showerror("Error!", "Folder " + requested_dir + " already exists.")

    if success:
        folder_frame_target_dir.config(text=CurrentDir)
        Scanned_Images_number_str.set(str(CurrentFrame))
        SessionData["CurrentDir"] = str(CurrentDir)
        SessionData["CurrentFrame"] = str(CurrentFrame)


def get_last_frame_dismiss():
    last_frame_dlg.grab_release()
    last_frame_dlg.destroy()


def get_last_frame(last_frame):
    global last_frame_dlg
    last_frame_dlg = tk.Toplevel(win)
    last_frame_dlg.title("Last frame")
    # last_frame_dlg.geometry(f"300x100")
    last_frame_dlg.rowconfigure(0, weight=1)
    last_frame_dlg.columnconfigure(0, weight=1)

    last_frame_label = tk.Label(last_frame_dlg, text="Enter number of last captured frame")
    last_frame_label.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
    last_frame_int = tk.IntVar(value=0)
    last_frame_int.set(last_frame)
    last_frame_entry = tk.Entry(last_frame_dlg, textvariable=last_frame_int, width=6, font=("Arial", FontSize),
                                justify="right")
    last_frame_entry.grid(row=1, column=0, columnspan=2, padx=10, pady=5)
    last_frame_ok_btn = tk.Button(last_frame_dlg, text="OK", command=get_last_frame_dismiss)
    last_frame_ok_btn.grid(row=2, column=0, padx=10, pady=5)
    last_frame_dlg.protocol("WM_DELETE_WINDOW", get_last_frame_dismiss)  # intercept close button
    last_frame_dlg.transient(win)  # dialog window is related to main
    last_frame_dlg.wait_visibility()  # can't grab until window appears, so we wait
    last_frame_dlg.grab_set()  # ensure all input goes to our window
    last_frame_dlg.wait_window()  # block until window is destroyed
    return last_frame_int.get()


def set_existing_folder():
    global CurrentDir, CurrentFrame

    if not SimulatedRun:
        NewDir = filedialog.askdirectory(initialdir=CurrentDir, title="Select existing folder for capture")
    else:
        NewDir = filedialog.askdirectory(initialdir=CurrentDir,
                                         title="Select existing folder with snapshots for simulated run")
    if not NewDir:
        return

    # Get number of files and highest frame number in selected folder
    filecount = 0
    last_frame = 0
    for name in os.listdir(NewDir):
        if os.path.isfile(os.path.join(NewDir, name)):
            # Extract frame number using regular expression
            frame_number = re.findall(r'\d+', name)
            last_frame = max(last_frame, int(frame_number[0]))  # Only one number in the filename, so we take the first
            filecount += 1

    current_frame_str = str(get_last_frame(last_frame))

    if current_frame_str is None:
        current_frame_str = '0'

    if current_frame_str == '':
        current_frame_str = '0'
    NewCurrentFrame = int(current_frame_str)

    if filecount > 0 and NewCurrentFrame < last_frame:
        confirm = tk.messagebox.askyesno(title='Files exist in target folder',
                                         message=f"Newly selected folder already contains {filecount} files."
                                                 f"\r\nSetting {NewCurrentFrame} as last captured frame will overwrite "
                                                 f"{last_frame - NewCurrentFrame} frames."
                                                 "Are you sure you want to continue?")
    else:
        confirm = True

    if confirm:
        CurrentFrame = NewCurrentFrame
        CurrentDir = NewDir

        Scanned_Images_number_str.set(str(current_frame_str))
        SessionData["CurrentFrame"] = str(CurrentFrame)

        folder_frame_target_dir.config(text=CurrentDir)
        SessionData["CurrentDir"] = str(CurrentDir)


def set_auto_wb():
    global manual_wb_red_value, manual_wb_blue_value

    if not ExpertMode:
        return

    SessionData["CurrentAwbAuto"] = AWB_enabled.get()
    SessionData["GainRed"] = wb_red_value.get()
    SessionData["GainBlue"] = wb_blue_value.get()

    if AWB_enabled.get():
        manual_wb_red_value = wb_red_value.get()
        manual_wb_blue_value = wb_blue_value.get()
        auto_wb_red_btn.config(text="AWB Red:")
        auto_wb_blue_btn.config(text="AWB Blue:")
        auto_wb_wait_btn.config(state=NORMAL)
        if not SimulatedRun and not CameraDisabled:
            camera.set_controls({"AwbEnable": True})
    else:
        wb_red_value.set(manual_wb_red_value)
        wb_blue_value.set(manual_wb_blue_value)
        auto_wb_red_btn.config(text="WB Red:")
        auto_wb_blue_btn.config(text="WB Blue:")
        auto_wb_wait_btn.config(state=DISABLED)
        if not SimulatedRun and not CameraDisabled:
            # Do not retrieve current gain values from Camera (capture_metadata) to prevent conflicts
            # Since we update values in the UI regularly, use those.
            camera_colour_gains = (wb_red_value.get(), wb_blue_value.get())
            camera.set_controls({"AwbEnable": False})
            camera.set_controls({"ColourGains": camera_colour_gains})
    arrange_widget_state(not AWB_enabled.get(), [auto_wb_wait_btn])
    arrange_widget_state(AWB_enabled.get(), [wb_red_spinbox, wb_blue_spinbox])
    arrange_widget_state(not AWB_enabled.get(), [AwbMode_label, AwbMode_dropdown])


def auto_white_balance_change_pause_selection():
    SessionData["AwbPause"] = auto_white_balance_change_pause.get()


def Manual_scan_activated_selection():
    global ManualScanEnabled
    ManualScanEnabled = Manual_scan_activated.get()
    manual_scan_advance_fraction_5_btn.config(state=NORMAL if ManualScanEnabled else DISABLED)
    manual_scan_advance_fraction_20_btn.config(state=NORMAL if ManualScanEnabled else DISABLED)
    manual_scan_take_snap_btn.config(state=NORMAL if ManualScanEnabled else DISABLED)


def manual_scan_advance_frame_fraction(steps):
    if not ExperimentalMode:
        return
    if not SimulatedRun:
        send_arduino_command(CMD_ADVANCE_FRAME_FRACTION, steps)
        time.sleep(0.2)
        capture('preview')
        time.sleep(0.2)


def manual_scan_advance_frame_fraction_5():
    manual_scan_advance_frame_fraction(5)


def manual_scan_advance_frame_fraction_20():
    manual_scan_advance_frame_fraction(20)


def manual_scan_take_snap():
    if not ExperimentalMode:
        return
    if not SimulatedRun:
        capture('manual')
        time.sleep(0.2)
        send_arduino_command(CMD_ADVANCE_FRAME)
        time.sleep(0.2)
        capture('preview')
        time.sleep(0.2)


def rwnd_speed_down():
    global rwnd_speed_delay

    if not SimulatedRun:
        send_arduino_command(CMD_INCREASE_WIND_SPEED)
    if rwnd_speed_delay + rwnd_speed_delay * 0.1 < 4000:
        rwnd_speed_delay += rwnd_speed_delay * 0.1
    else:
        rwnd_speed_delay = 4000
    rwnd_speed_control_spinbox.config(text=str(round(60 / (rwnd_speed_delay * 375 / 1000000))) + 'rpm')


def rwnd_speed_up():
    global rwnd_speed_delay

    if not SimulatedRun:
        send_arduino_command(CMD_DECREASE_WIND_SPEED)
    if rwnd_speed_delay - rwnd_speed_delay * 0.1 > 200:
        rwnd_speed_delay -= rwnd_speed_delay * 0.1
    else:
        rwnd_speed_delay = 200
    rwnd_speed_control_spinbox.config(text=str(round(60 / (rwnd_speed_delay * 375 / 1000000))) + 'rpm')


def frame_extra_steps_selection():
    aux = value_normalize(frame_extra_steps_value, -30, 30, 0)
    SessionData["FrameExtraSteps"] = aux
    send_arduino_command(CMD_SET_EXTRA_STEPS, aux)


def button_status_change_except(except_button, active):
    global button_lock_counter
    general_widget_list = [SingleStep_btn, Snapshot_btn, AdvanceMovie_btn, Rewind_btn, FastForward_btn,
                           negative_image_checkbox,
                           Exit_btn, film_type_S8_rb, film_type_R8_rb, file_type_dropdown, new_folder_btn,
                           real_time_display_checkbox,
                           resolution_label, resolution_dropdown, file_type_label, file_type_dropdown,
                           existing_folder_btn, hdr_capture_active_checkbox]
    control_widget_list = [auto_exposure_btn, exposure_spinbox, auto_exposure_wait_btn, auto_wb_red_btn, wb_red_spinbox,
                           auto_wb_wait_btn, auto_wb_blue_btn, wb_blue_spinbox, match_wait_margin_spinbox,
                           AeConstraintMode_dropdown, AeMeteringMode_dropdown, AeExposureMode_dropdown,
                           AwbMode_dropdown, brightness_spinbox, contrast_spinbox, saturation_spinbox,
                           analogue_gain_spinbox, sharpness_spinbox, exposure_compensation_spinbox,
                           steps_per_frame_spinbox, pt_level_spinbox, frame_fine_tune_spinbox,
                           frame_extra_steps_spinbox, scan_speed_spinbox, stabilization_delay_spinbox,
                           pt_level_btn, steps_per_frame_btn, hdr_bracket_width_auto_checkbox]
    hdr_widget_list = [hdr_min_exp_spinbox, hdr_max_exp_spinbox, hdr_bracket_width_spinbox,
                       hdr_bracket_shift_spinbox, hdr_merge_in_place_checkbox]
    experimental_widget_list = [RetreatMovie_btn, Free_btn, Manual_scan_checkbox]

    if active:
        button_lock_counter += 1
    else:
        button_lock_counter -= 1

    if button_lock_counter > 1 or (not active and button_lock_counter > 0):
        return

    for widget in general_widget_list:
        if except_button != widget:
            widget.config(state=DISABLED if active else NORMAL)

    if not keep_control_widgets_enabled:
        for widget in control_widget_list:
            if except_button != widget:
                widget.config(state=DISABLED if active else NORMAL)
        if hdr_capture_active:
            for widget in hdr_widget_list:
                if except_button != widget:
                    widget.config(state=DISABLED if active else NORMAL)

    if ExperimentalMode:
        for widget in experimental_widget_list:
            if except_button != widget:
                widget.config(state=DISABLED if active else NORMAL)

    if except_button != real_time_zoom_checkbox:
        real_time_zoom_checkbox.config(state=NORMAL if real_time_display.get() else DISABLED)
    if except_button != Start_btn and not PiCam2PreviewEnabled:
        Start_btn.config(state=DISABLED if active else NORMAL)


def advance_movie(from_arduino=False):
    global AdvanceMovieActive

    # Update button text
    if not AdvanceMovieActive:  # Advance movie is about to start...
        AdvanceMovie_btn.config(text='Stop movie', bg='red',
                                fg='white', relief=SUNKEN)  # ...so now we propose to stop it in the button test
    else:
        AdvanceMovie_btn.config(text='Movie forward', bg=save_bg,
                                fg=save_fg, relief=RAISED)  # Otherwise change to default text to start the action
    AdvanceMovieActive = not AdvanceMovieActive
    # Send instruction to Arduino
    if not SimulatedRun and not from_arduino:  # Do not send Arduino command if triggered by Arduino response
        send_arduino_command(CMD_FILM_FORWARD)

    # Enable/Disable related buttons
    button_status_change_except(AdvanceMovie_btn, AdvanceMovieActive)


def retreat_movie():
    global RetreatMovieActive

    # Update button text
    if not RetreatMovieActive:  # Advance movie is about to start...
        RetreatMovie_btn.config(text='Stop movie', bg='red',
                                fg='white', relief=SUNKEN)  # ...so now we propose to stop it in the button test
    else:
        RetreatMovie_btn.config(text='Movie backward', bg=save_bg,
                                fg=save_fg, relief=RAISED)  # Otherwise change to default text to start the action
    RetreatMovieActive = not RetreatMovieActive
    # Send instruction to Arduino
    if not SimulatedRun:
        send_arduino_command(CMD_FILM_BACKWARD)

    # Enable/Disable related buttons
    button_status_change_except(RetreatMovie_btn, RetreatMovieActive)


def rewind_movie():
    global RewindMovieActive
    global RewindErrorOutstanding, RewindEndOutstanding

    if SimulatedRun and RewindMovieActive:  # no callback from Arduino in simulated mode
        RewindEndOutstanding = True

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not RewindMovieActive:  # Ask only when rewind is not ongoing
        RewindMovieActive = True
        # Update button text
        Rewind_btn.config(text='Stop\n<<', bg='red', fg='white',
                          relief=SUNKEN)  # ...so now we propose to stop it in the button test
        # Enable/Disable related buttons
        button_status_change_except(Rewind_btn, RewindMovieActive)
        # Invoke rewind_loop to continue processing until error or end event
        win.after(5, rewind_loop)
    elif RewindErrorOutstanding:
        confirm = tk.messagebox.askyesno(title='Error during rewind',
                                         message='It seems there is film loaded via filmgate. \
                                         \r\nAre you sure you want to proceed?')
        if confirm:
            time.sleep(0.2)
            if not SimulatedRun:
                send_arduino_command(CMD_UNCONDITIONAL_REWIND)  # Forced rewind, no filmgate check
                # Invoke fast_forward_loop a first time when fast-forward starts
                win.after(5, rewind_loop)
        else:
            RewindMovieActive = False
    elif RewindEndOutstanding:
        RewindMovieActive = False

    if not RewindMovieActive:
        Rewind_btn.config(text='<<', bg=save_bg, fg=save_fg,
                          relief=RAISED)  # Otherwise change to default text to start the action
        # Enable/Disable related buttons
        button_status_change_except(Rewind_btn, RewindMovieActive)

    if not RewindErrorOutstanding and not RewindEndOutstanding:  # invoked from button
        time.sleep(0.2)
        if not SimulatedRun:
            send_arduino_command(CMD_REWIND)

    if RewindErrorOutstanding:
        RewindErrorOutstanding = False
    if RewindEndOutstanding:
        RewindEndOutstanding = False


def rewind_loop():
    if RewindMovieActive:
        # Invoke rewind_loop one more time, as long as rewind is ongoing
        if not RewindErrorOutstanding and not RewindEndOutstanding:
            win.after(5, rewind_loop)
        else:
            rewind_movie()


def fast_forward_movie():
    global FastForwardActive
    global FastForwardErrorOutstanding, FastForwardEndOutstanding

    if SimulatedRun and FastForwardActive:  # no callback from Arduino in simulated mode
        FastForwardEndOutstanding = True

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not FastForwardActive:  # Ask only when rewind is not ongoing
        FastForwardActive = True
        # Update button text
        FastForward_btn.config(text='Stop\n>>', bg='red', fg='white', relief=SUNKEN)
        # Enable/Disable related buttons
        button_status_change_except(FastForward_btn, FastForwardActive)
        # Invoke fast_forward_loop a first time when fast-forward starts
        win.after(5, fast_forward_loop)
    elif FastForwardErrorOutstanding:
        confirm = tk.messagebox.askyesno(title='Error during fast forward',
                                         message='It seems there is film loaded via filmgate. \
                                         \r\nAre you sure you want to proceed?')
        if confirm:
            time.sleep(0.2)
            if not SimulatedRun:
                send_arduino_command(CMD_UNCONDITIONAL_FAST_FORWARD)  # Forced FF, no filmgate check
                # Invoke fast_forward_loop a first time when fast-forward starts
                win.after(5, fast_forward_loop)
        else:
            FastForwardActive = False
    elif FastForwardEndOutstanding:
        FastForwardActive = False

    if not FastForwardActive:
        FastForward_btn.config(text='>>', bg=save_bg, fg=save_fg, relief=RAISED)
        # Enable/Disable related buttons
        button_status_change_except(FastForward_btn, FastForwardActive)

    if not FastForwardErrorOutstanding and not FastForwardEndOutstanding:  # invoked from button
        time.sleep(0.2)
        if not SimulatedRun:
            send_arduino_command(CMD_FAST_FORWARD)

    if FastForwardErrorOutstanding:
        FastForwardErrorOutstanding = False
    if FastForwardEndOutstanding:
        FastForwardEndOutstanding = False


def fast_forward_loop():
    if FastForwardActive:
        # Invoke fast_forward_loop one more time, as long as rewind is ongoing
        if not FastForwardErrorOutstanding and not FastForwardEndOutstanding:
            win.after(5, fast_forward_loop)
        else:
            fast_forward_movie()


# *******************************************************************
# ********************** Capture functions **************************
# *******************************************************************
def reverse_image(image):
    image_array = np.asarray(image)
    image_array = np.negative(image_array)
    return Image.fromarray(image_array)


def capture_display_thread(queue, event, id):
    global active_threads
    logging.debug("Started capture_display_thread")
    while not event.is_set() or not queue.empty():
        message = queue.get()
        curtime = time.time()
        if ExitingApp:
            break
        logging.debug("Retrieved message from capture display queue (len=%i)", queue.qsize())
        if message == END_TOKEN:
            break
        type = message[0]
        if type != IMAGE_TOKEN:
            continue
        image = message[1]
        curframe = message[2]
        hdr_idx = message[3]

        # If too many items in queue the skip display
        if (MaxQueueSize - queue.qsize() <= 5):
            logging.warning("Display queue almost full: Skipping frame display")
        else:
            draw_preview_image(image, curframe, hdr_idx)
            logging.debug("Display thread complete: %s ms", str(round((time.time() - curtime) * 1000, 1)))
    active_threads -= 1
    logging.debug("Exiting capture_display_thread")


def capture_save_thread(queue, event, id):
    global ScanStopRequested
    global active_threads
    global total_wait_time_save_image

    if os.path.isdir(CurrentDir):
        os.chdir(CurrentDir)
    else:
        logging.error("Target dir %s unmounted: Stop scan session", CurrentDir)
        ScanStopRequested = True  # If target dir does not exist, stop scan
        return
    logging.debug("Started capture_save_thread n.%i", id)
    while not event.is_set() or not queue.empty():
        message = queue.get()
        curtime = time.time()
        logging.debug("Thread %i: Retrieved message from capture save queue", id)
        if ExitingApp:
            break
        if message == END_TOKEN:
            break
        # Invert image if button selected
        is_dng = file_type_dropdown_selected.get() == 'dng'
        is_jpg = file_type_dropdown_selected.get() == 'jpg'
        # Extract info from message
        type = message[0]
        if type == REQUEST_TOKEN:
            request = message[1]
        elif type == IMAGE_TOKEN:
            if is_dng:
                logging.error("Cannot save plain image to DNG file.")
                ScanStopRequested = True  # If target dir does not exist, stop scan
                return
            captured_image = message[1]
        else:
            logging.error(f"Invalid message type received: {type}")
        frame_idx = message[2]
        hdr_idx = message[3]
        if is_dng:
            # Saving DNG implies passing a request, not an image, therefore no additional checks (no negative allowed)
            if hdr_idx > 1:  # Hdr frame 1 has standard filename
                request.save_dng(HdrFrameFilenamePattern % (frame_idx, hdr_idx, file_type_dropdown_selected.get()))
            else:  # Non HDR
                request.save_dng(FrameFilenamePattern % (frame_idx, file_type_dropdown_selected.get()))
            request.release()
            logging.debug("Thread %i saved request DNG image: %s ms", id,
                          str(round((time.time() - curtime) * 1000, 1)))
        else:
            # If not is_dng AND negative_image AND request: Convert to image now, and do a PIL save
            if not negative_image.get() and type == REQUEST_TOKEN:
                if hdr_idx > 1:  # Hdr frame 1 has standard filename
                    request.save('main',
                                 HdrFrameFilenamePattern % (frame_idx, hdr_idx, file_type_dropdown_selected.get()))
                else:  # Non HDR
                    request.save('main', FrameFilenamePattern % (frame_idx, file_type_dropdown_selected.get()))
                request.release()
                logging.debug("Thread %i saved request image: %s ms", id,
                              str(round((time.time() - curtime) * 1000, 1)))
            else:
                if hdr_idx > 1:  # Hdr frame 1 has standard filename
                    logging.debug("Saving HDR frame n.%i", hdr_idx)
                    captured_image.save(
                        HdrFrameFilenamePattern % (frame_idx, hdr_idx, file_type_dropdown_selected.get()), quality=95)
                else:
                    captured_image.save(FrameFilenamePattern % (frame_idx, file_type_dropdown_selected.get()),
                                        quality=95)
                logging.debug("Thread %i saved image: %s ms", id,
                              str(round((time.time() - curtime) * 1000, 1)))
        aux = time.time() - curtime
        total_wait_time_save_image += aux
        time_save_image.add_value(aux)
    active_threads -= 1
    logging.debug("Exiting capture_save_thread n.%i", id)


def draw_preview_image(preview_image, curframe, idx):
    global total_wait_time_preview_display

    curtime = time.time()

    if curframe % preview_module_value.get() == 0 and preview_image is not None:
        if idx == 0 or (idx == 2 and not HdrViewX4Active):
            preview_image = preview_image.resize((PreviewWidth, PreviewHeight))
            PreviewAreaImage = ImageTk.PhotoImage(preview_image)
        elif HdrViewX4Active:
            # if using View4X mode and there are 5 exposures, we do not display the 5th
            # and if there are 3, 4th position will always be empty
            quarter_image = preview_image.resize((int(PreviewWidth / 2), int(PreviewHeight / 2)))
            if idx == 1:
                hdr_view_4_image.paste(quarter_image, (0, 0))
            elif idx == 2:
                hdr_view_4_image.paste(quarter_image, (int(PreviewWidth / 2), 0))
            elif idx == 3:
                hdr_view_4_image.paste(quarter_image, (0, int(PreviewHeight / 2)))
            elif idx == 4:
                hdr_view_4_image.paste(quarter_image, (int(PreviewWidth / 2), int(PreviewHeight / 2)))
            PreviewAreaImage = ImageTk.PhotoImage(hdr_view_4_image)

        if idx == 0 or (idx == 2 and not HdrViewX4Active) or HdrViewX4Active:
            # The Label widget is a standard Tkinter widget used to display a text or image on the screen.
            # next two lines to avoid flickering. However, they might cause memory problems
            draw_capture_canvas.create_image(0, 0, anchor=NW, image=PreviewAreaImage)
            draw_capture_canvas.image = PreviewAreaImage

            # The Pack geometry manager packs widgets in rows or columns.
            # draw_capture_label.place(x=0, y=0) # This line is probably causing flickering, to be checked

    aux = time.time() - curtime
    total_wait_time_preview_display += aux
    time_preview_display.add_value(aux)
    logging.debug("Display preview image: %s ms", str(round((time.time() - curtime) * 1000, 1)))


def capture_single_step():
    if not SimulatedRun:
        capture('still')


def single_step_movie():
    global camera

    if not SimulatedRun:
        send_arduino_command(CMD_SINGLE_STEP)

        if not CameraDisabled:
            # If no camera preview, capture frame in memory and display it
            # Single step is not a critical operation, waiting 100ms for it to happen should be enough
            # No need to implement confirmation from Arduino, as we have for regular capture during scan
            time.sleep(0.5)
            single_step_image = camera.capture_image("main")
            draw_preview_image(single_step_image, 0, 0)


def emergency_stop():
    if not SimulatedRun:
        send_arduino_command(90)


def update_rpi_temp():
    global RPiTemp
    if not SimulatedRun:
        file = open('/sys/class/thermal/thermal_zone0/temp', 'r')
        temp_str = file.readline()
        file.close()
        RPiTemp = int(int(temp_str) / 100) / 10
    else:
        RPiTemp = 64.5


def disk_space_available():
    global available_space_mb, disk_space_error_to_notify

    if not check_disk_space:
        return True
    disk_usage = psutil.disk_usage(CurrentDir)
    available_space_mb = disk_usage.free / (1024 ** 2)

    if available_space_mb < 500:
        logging.debug(f"Disk space running out, only {available_space_mb} MB available")
        disk_space_error_to_notify = True
        return False
    else:
        return True


def hdr_set_controls():
    if not ExperimentalMode:
        return
    hdr_viewx4_active_checkbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_min_exp_label.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_min_exp_spinbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_max_exp_label.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_max_exp_spinbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_width_label.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_shift_label.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_width_spinbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_shift_spinbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_width_auto_checkbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_merge_in_place_checkbox.config(state=NORMAL if HdrCaptureActive else DISABLED)


def switch_hdr_capture():
    global HdrCaptureActive
    global max_inactivity_delay

    HdrCaptureActive = hdr_capture_active.get()
    SessionData["HdrCaptureActive"] = str(HdrCaptureActive)

    hdr_set_controls()
    if HdrCaptureActive:  # If HDR enabled, handle automatic control settings for widgets
        max_inactivity_delay = max_inactivity_delay * 2
        arrange_widget_state(hdr_bracket_auto.get(), [hdr_min_exp_spinbox, hdr_max_exp_spinbox])
    else:  # If disabling HDR, need to set standard exposure as set in UI
        max_inactivity_delay = int(max_inactivity_delay / 2)
        if AE_enabled.get():  # Automatic mode
            CurrentExposure = 0
        else:
            if not SimulatedRun and not CameraDisabled:
                # Since we are in auto exposure mode, retrieve current value to start from there
                metadata = camera.capture_metadata()
                CurrentExposure = metadata["ExposureTime"]
            else:
                CurrentExposure = 3500  # Arbitrary Value for Simulated run
        if not SimulatedRun and not CameraDisabled:
            camera.set_controls({"AeEnable": True if CurrentExposure == 0 else False})
        SessionData["CurrentExposure"] = CurrentExposure
        exposure_value.set(CurrentExposure)
    send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
    logging.debug(f"max_inactivity_delay: {max_inactivity_delay}")


def switch_hdr_viewx4():
    global HdrViewX4Active
    HdrViewX4Active = hdr_viewx4_active.get()
    SessionData["HdrViewX4Active"] = str(HdrViewX4Active)


def set_negative_image():
    SessionData["NegativeCaptureActive"] = negative_image.get()


def toggle_ui_size():
    global app_width, app_height

    if toggle_ui_small.get():
        extended_frame.pack_forget()
    else:
        extended_frame.pack(side=LEFT, padx=10, expand=True, fill=tk.Y, anchor="center")
    # Prevent window resize
    win.minsize(app_width, app_height)
    win.maxsize(app_width, app_height)
    win.geometry(f'{app_width}x{app_height - 20}')  # setting the size of the window


# Function to enable 'real' preview with PiCamera2
# Even if it is useless for capture (slow and imprecise) it is still needed for other tasks like:
#  - Focus
#  - Color adjustment
#  - Exposure adjustment
def set_real_time_display():
    if real_time_display.get():
        logging.debug("Real time display enabled")
    else:
        logging.debug("Real time display disabled")
    if not SimulatedRun and not CameraDisabled:
        if real_time_display.get():
            if camera._preview:
                camera.stop_preview()
            time.sleep(0.1)
            camera.start_preview(Preview.QTGL, x=PreviewWinX, y=PreviewWinY, width=840, height=720)
            time.sleep(0.1)
            camera.switch_mode(preview_config)
        else:
            if camera._preview:
                camera.stop_preview()
            camera.stop()
            camera.start()
            time.sleep(0.1)
            camera.switch_mode(capture_config)

    # Do not allow scan to start while PiCam2 preview is active
    Start_btn.config(state=DISABLED if real_time_display.get() else NORMAL)
    real_time_zoom_checkbox.config(state=NORMAL if real_time_display.get() else DISABLED)
    real_time_zoom_checkbox.deselect()
    real_time_display_checkbox.config(state=NORMAL)


def set_s8():
    global PreviewHeight, FilmHoleY_Top, FilmHoleY_Bottom

    SessionData["FilmType"] = "S8"
    time.sleep(0.2)

    PTLevel = PTLevelS8
    MinFrameSteps = MinFrameStepsS8
    if ALT_scann_init_done:
        SessionData["PTLevel"] = PTLevel
        SessionData["MinFrameSteps"] = MinFrameSteps
    if ExpertMode:
        pt_level_value.set(PTLevel)
        steps_per_frame_value.set(MinFrameSteps)
    # Size and position of hole markers
    FilmHoleY_Top = int(PreviewHeight / 2.6)
    FilmHoleY_Bottom = FilmHoleY_Top
    film_hole_frame_top.place(x=0, y=FilmHoleY_Top, height=FilmHoleHeightTop)
    film_hole_frame_bottom.place(x=0, y=FilmHoleY_Bottom, height=FilmHoleHeightBottom)
    if not SimulatedRun:
        send_arduino_command(CMD_SET_SUPER_8)
        send_arduino_command(CMD_SET_PT_LEVEL, 0 if auto_pt_level_enabled.get() else PTLevel)
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if auto_framesteps_enabled.get() else MinFrameSteps)


def set_r8():
    global film_hole_frame_top, film_hole_frame_bottom
    global PreviewHeight, FilmHoleY_Top, FilmHoleY_Bottom, FilmHoleHeightTop, FilmHoleHeightBottom

    SessionData["FilmType"] = "R8"
    time.sleep(0.2)

    PTLevel = PTLevelR8
    MinFrameSteps = MinFrameStepsR8
    if ALT_scann_init_done:
        SessionData["PTLevel"] = PTLevel
        SessionData["MinFrameSteps"] = MinFrameSteps
    if ExpertMode:
        pt_level_value.set(PTLevel)
        steps_per_frame_value.set(MinFrameSteps)
    # Size and position of hole markers
    FilmHoleY_Top = 6
    FilmHoleY_Bottom = int(PreviewHeight / 1.25)
    film_hole_frame_top.place(x=0, y=FilmHoleY_Top, height=FilmHoleHeightTop)
    film_hole_frame_bottom.place(x=0, y=FilmHoleY_Bottom, height=FilmHoleHeightBottom)
    if not SimulatedRun:
        send_arduino_command(CMD_SET_REGULAR_8)
        send_arduino_command(CMD_SET_PT_LEVEL, 0 if auto_pt_level_enabled.get() else PTLevel)
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if auto_framesteps_enabled.get() else MinFrameSteps)


def register_frame():
    global FPM_StartTime
    global FPM_CalculatedValue

    # Get current time
    frame_time = time.time()
    # Determine if we should start new count (last capture older than 5 seconds)
    if len(FPM_LastMinuteFrameTimes) == 0 or FPM_LastMinuteFrameTimes[-1] < frame_time - 30:
        FPM_StartTime = frame_time
        FPM_LastMinuteFrameTimes.clear()
        FPM_CalculatedValue = -1
    # Add current time to list
    FPM_LastMinuteFrameTimes.append(frame_time)
    # Remove entries older than one minute
    FPM_LastMinuteFrameTimes.sort()
    while FPM_LastMinuteFrameTimes[0] <= frame_time - 60:
        FPM_LastMinuteFrameTimes.remove(FPM_LastMinuteFrameTimes[0])
    # Calculate current value, only if current count has been going for more than 10 seconds
    if frame_time - FPM_StartTime > 60:  # no calculations needed, frames in list are all in the last 60 seconds
        FPM_CalculatedValue = len(FPM_LastMinuteFrameTimes)
    elif frame_time - FPM_StartTime > 10:  # some  calculations needed if less than 60 sec
        FPM_CalculatedValue = int((len(FPM_LastMinuteFrameTimes) * 60) / (frame_time - FPM_StartTime))


def adjust_hdr_bracket_auto():
    if not HdrCaptureActive:
        return

    SessionData["HdrBracketAuto"] = hdr_bracket_auto.get()

    arrange_widget_state(hdr_bracket_auto.get(), [hdr_max_exp_spinbox, hdr_min_exp_spinbox])


def adjust_merge_in_place():
    if not HdrCaptureActive:
        return

    SessionData["HdrMergeInPlace"] = hdr_merge_in_place.get()


def adjust_hdr_bracket():
    global recalculate_hdr_exp_list
    global hdr_best_exp
    global PreviousCurrentExposure
    global force_adjust_hdr_bracket

    if not HdrCaptureActive:
        return

    if SimulatedRun or CameraDisabled:
        aux_current_exposure = 20
    else:
        camera.set_controls({"AeEnable": True})
        for i in range(1, dry_run_iterations * 2):
            camera.capture_image("main")

        # Since we are in auto exposure mode, retrieve current value to start from there
        metadata = camera.capture_metadata()
        aux_current_exposure = int(metadata["ExposureTime"] / 1000)
        camera.set_controls({"AeEnable": False})

    # Adjust only if auto exposure changes
    if aux_current_exposure != PreviousCurrentExposure or force_adjust_hdr_bracket:
        logging.debug(f"Adjusting bracket, prev/cur exp: {PreviousCurrentExposure} -> {aux_current_exposure}")
        force_adjust_hdr_bracket = False
        PreviousCurrentExposure = aux_current_exposure
        hdr_best_exp = aux_current_exposure
        hdr_min_exp_value.set(max(hdr_best_exp - int(hdr_bracket_width_value.get() / 2), hdr_lower_exp))
        hdr_max_exp_value.set(hdr_min_exp_value.get() + hdr_bracket_width_value.get())
        SessionData["HdrMinExp"] = hdr_min_exp_value.get()
        SessionData["HdrMaxExp"] = hdr_max_exp_value.get()
        recalculate_hdr_exp_list = True
        logging.debug(f"Adjusting bracket: {hdr_min_exp_value.get()}, {hdr_max_exp_value.get()}")


def capture_hdr(mode):
    global recalculate_hdr_exp_list

    if hdr_bracket_auto.get() and session_frames % hdr_auto_bracket_frames == 0:
        adjust_hdr_bracket()

    if recalculate_hdr_exp_list:
        hdr_reinit()
        perform_dry_run = True
        recalculate_hdr_exp_list = False
    else:
        perform_dry_run = False

    images_to_merge.clear()
    # session_frames should be equal to 1 for the first captured frame of the scan session.
    # For HDR this means we need to unconditionally wait for exposure adaptation
    # For following frames, we can skip dry run for the first capture since we alternate the sense of the exposures
    # on each frame
    if session_frames == 1:
        perform_dry_run = True

    if session_frames % 2 == 1:
        work_list = hdr_exp_list
        idx = 1
        idx_inc = 1
    else:
        work_list = hdr_rev_exp_list
        idx = hdr_num_exposures
        idx_inc = -1
    is_dng = file_type_dropdown_selected.get() == 'dng'
    is_png = file_type_dropdown_selected.get() == 'png'
    for exp in work_list:
        exp = max(1, exp + hdr_bracket_shift_value.get())  # Apply bracket shift
        logging.debug("capture_hdr: exp %.2f", exp)
        if perform_dry_run:
            camera.set_controls({"ExposureTime": int(exp * 1000)})
        else:
            time.sleep(stabilization_delay_value.get() / 1000)  # Allow time to stabilize image only if no dry run
        if perform_dry_run:
            for i in range(1, dry_run_iterations):  # Perform a few dummy captures to allow exposure stabilization
                camera.capture_image("main")
        # We skip dry run only for the first capture of each frame,
        # as it is the same exposure as the last capture of the previous one
        perform_dry_run = True
        # For PiCamera2, preview and save to file are handled in asynchronous threads
        if hdr_merge_in_place.get() and not is_dng:  # For now we do not even try to merge DNG images in place
            captured_image = camera.capture_image("main")  # If merge in place, Capture snapshot (no DNG allowed)
            # Convert Pillow image to NumPy array
            img_np = np.array(captured_image)
            # Convert the NumPy array to a format suitable for MergeMertens (e.g., float32)
            img_np_float32 = img_np.astype(np.float32)
            images_to_merge.append(img_np_float32)  # Add frame
        else:
            if is_dng or is_png:  # If not using DNG we can still use multithread (if not disabled)
                # DNG + HDR, save threads not possible due to request conflicting with retrieve metadata
                request = camera.capture_request(capture_config)
                if CurrentFrame % preview_module_value.get() == 0:
                    captured_image = request.make_image('main')
                    # Display preview using thread, not directly
                    queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, idx))
                    capture_display_queue.put(queue_item)
                curtime = time.time()
                if idx > 1:  # Hdr frame 1 has standard filename
                    request.save_dng(HdrFrameFilenamePattern % (CurrentFrame, idx, file_type_dropdown_selected.get()))
                else:  # Non HDR
                    request.save_dng(FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()))
                request.release()
                logging.debug(f"Capture hdr, saved request image ({CurrentFrame}, {idx}: "
                              f"{round((time.time() - curtime) * 1000, 1)}")
            else:
                captured_image = camera.capture_image("main")
                if negative_image.get():
                    captured_image = reverse_image(captured_image)
                if DisableThreads:  # Save image in main loop
                    curtime = time.time()
                    draw_preview_image(captured_image, CurrentFrame, idx)
                    if idx > 1:  # Hdr frame 1 has standard filename
                        captured_image.save(
                            HdrFrameFilenamePattern % (CurrentFrame, idx, file_type_dropdown_selected.get()))
                    else:
                        captured_image.save(FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()))
                    logging.debug(f"Capture hdr, saved image ({CurrentFrame}, {idx}): "
                                  f"{round((time.time() - curtime) * 1000, 1)} ms")
                else:  # send image to threads
                    if mode == 'normal' or mode == 'manual':  # Do not save in preview mode, only display
                        # In HDR we cannot really pass a request to the thread since it will interfere with the
                        # dry run captures done in the main capture loop. Maybe with synchronization it could be
                        # made to work, but then the small advantage offered by threads would be lost
                        queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, idx))
                        if CurrentFrame % preview_module_value.get() == 0:
                            # Display preview using thread, not directly
                            capture_display_queue.put(queue_item)
                        capture_save_queue.put(queue_item)
                        logging.debug(f"Queueing hdr image ({CurrentFrame}, {idx})")
        idx += idx_inc
    if hdr_merge_in_place.get() and not is_dng:
        # Perform merge of the HDR image list
        img = MergeMertens.process(images_to_merge)
        # Convert the result back to PIL
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
        img = Image.fromarray(img)
        if CurrentFrame % preview_module_value.get() == 0:
            # Display preview using thread, not directly
            queue_item = tuple((IMAGE_TOKEN, img, CurrentFrame, 0))
            capture_display_queue.put(queue_item)
        img.save(FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()), quality=95)


def capture_single(mode):
    global CurrentFrame
    global total_wait_time_save_image

    is_dng = file_type_dropdown_selected.get() == 'dng'
    is_png = file_type_dropdown_selected.get() == 'png'
    curtime = time.time()
    if not DisableThreads:
        if is_dng or is_png:  # Save as request only for DNG captures
            request = camera.capture_request(capture_config)
            # For PiCamera2, preview and save to file are handled in asynchronous threads
            if CurrentFrame % preview_module_value.get() == 0:
                captured_image = request.make_image('main')
                # Display preview using thread, not directly
                queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, 0))
                capture_display_queue.put(queue_item)
            else:
                time_preview_display.add_value(0)
            if mode == 'normal' or mode == 'manual':  # Do not save in preview mode, only display
                save_queue_item = tuple((REQUEST_TOKEN, request, CurrentFrame, 0))
                capture_save_queue.put(save_queue_item)
                logging.debug(f"Queueing frame ({CurrentFrame}")
        else:
            captured_image = camera.capture_image("main")
            if negative_image.get():
                captured_image = reverse_image(captured_image)
            queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, 0))
            # For PiCamera2, preview and save to file are handled in asynchronous threads
            if CurrentFrame % preview_module_value.get() == 0:
                # Display preview using thread, not directly
                capture_display_queue.put(queue_item)
            else:
                time_preview_display.add_value(0)
            if mode == 'normal' or mode == 'manual':  # Do not save in preview mode, only display
                capture_save_queue.put(queue_item)
                logging.debug(f"Queuing frame {CurrentFrame}")
        if mode == 'manual':  # In manual mode, increase CurrentFrame
            CurrentFrame += 1
            # Update number of captured frames
            Scanned_Images_number_str.set(str(CurrentFrame))
    else:
        if is_dng or is_png:
            request = camera.capture_request(capture_config)
            if CurrentFrame % preview_module_value.get() == 0:
                captured_image = request.make_image('main')
            else:
                captured_image = None
            draw_preview_image(captured_image, CurrentFrame, 0)
            if mode == 'normal' or mode == 'manual':  # Do not save in preview mode, only display
                request.save_dng(FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()))
                logging.debug(f"Saving DNG frame ({CurrentFrame}: {round((time.time() - curtime) * 1000, 1)}")
            request.release()
        else:
            captured_image = camera.capture_image("main")
            if negative_image.get():
                captured_image = reverse_image(captured_image)
            draw_preview_image(captured_image, CurrentFrame, 0)
            captured_image.save(FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()), quality=95)
            logging.debug(
                f"Saving image ({CurrentFrame}: {round((time.time() - curtime) * 1000, 1)}")
        aux = time.time() - curtime
        total_wait_time_save_image += aux
        time_save_image.add_value(aux)
        if mode == 'manual':  # In manual mode, increase CurrentFrame
            CurrentFrame += 1
            # Update number of captured frames
            Scanned_Images_number_str.set(str(CurrentFrame))


# 4 possible modes:
# 'normal': Standard capture during automated scan (display and save)
# 'manual': Manual capture during manual scan (display and save)
# 'still': Button to capture still (specific filename)
# 'preview': Manual scan, display only, do not save
def capture(mode):
    global PreviousCurrentExposure
    global PreviousGainRed, PreviousGainBlue
    global total_wait_time_autoexp, total_wait_time_awb
    global CurrentStill

    if SimulatedRun or CameraDisabled:
        return

    os.chdir(CurrentDir)

    # Wait for auto exposure to adapt only if allowed (and if not using HDR)
    # If AE disabled, only enter as per preview_module to refresh values
    if AE_enabled.get() and not HdrCaptureActive and (
            auto_exposure_change_pause.get() or CurrentFrame % preview_module_value.get() == 0):
        curtime = time.time()
        wait_loop_count = 0
        while True:  # In case of exposure change, give time for the camera to adapt
            metadata = camera.capture_metadata()
            aux_current_exposure = metadata["ExposureTime"]
            if auto_exposure_change_pause.get():
                # With PiCamera2, exposure was changing too often, so level changed from 1000 to 2000, then to 4000
                # Finally changed to allow a percentage of the value used previously
                # As we initialize this percentage to 50%, we start with double the original value
                if abs(aux_current_exposure - PreviousCurrentExposure) > (
                        match_wait_margin_value.get() * Tolerance_AE) / 100:
                    if (wait_loop_count % 10 == 0):
                        logging.debug(
                            f"AE match: ({aux_current_exposure / 1000},Auto {PreviousCurrentExposure / 1000})")
                    wait_loop_count += 1
                    PreviousCurrentExposure = aux_current_exposure
                    time.sleep(0.2)
                    if (time.time() - curtime) * 1000 > max_wait_time:  # Never wait more than 5 seconds
                        break;
                else:
                    break
            else:
                break
        if wait_loop_count >= 0:
            exposure_value.set(aux_current_exposure / 1000)
            aux = time.time() - curtime
            total_wait_time_autoexp += aux
            time_autoexp.add_value(aux)
            logging.debug("AE match delay: %s ms", str(round((time.time() - curtime) * 1000, 1)))
    else:
        time_autoexp.add_value(0)

    # Wait for auto white balance to adapt only if allowed
    # If AWB disabled, only enter as per preview_module to refresh values
    if AWB_enabled.get() and (auto_white_balance_change_pause.get() or CurrentFrame % preview_module_value.get() == 0):
        curtime = time.time()
        wait_loop_count = 0
        while True:  # In case of exposure change, give time for the camera to adapt
            metadata = camera.capture_metadata()
            camera_colour_gains = metadata["ColourGains"]
            aux_gain_red = camera_colour_gains[0]
            aux_gain_blue = camera_colour_gains[1]
            if auto_white_balance_change_pause.get():
                # Same as for exposure, difference allowed is a percentage of the maximum value
                if abs(aux_gain_red - PreviousGainRed) >= (match_wait_margin_value.get() * Tolerance_AWB / 100) or \
                        abs(aux_gain_blue - PreviousGainBlue) >= (match_wait_margin_value.get() * Tolerance_AWB / 100):
                    if (wait_loop_count % 10 == 0):
                        aux_gains_str = "(" + str(round(aux_gain_red, 2)) + ", " + str(round(aux_gain_blue, 2)) + ")"
                        logging.debug("AWB Match: %s", aux_gains_str)
                    wait_loop_count += 1
                    PreviousGainRed = aux_gain_red
                    PreviousGainBlue = aux_gain_blue
                    time.sleep(0.2)
                    if (time.time() - curtime) * 1000 > max_wait_time:  # Never wait more than 5 seconds
                        break;
                else:
                    break
            else:
                break
        if wait_loop_count >= 0:
            if ExpertMode:
                wb_red_value.set(round(aux_gain_red, 1))
                wb_blue_value.set(round(aux_gain_blue, 1))
            aux = time.time() - curtime
            total_wait_time_awb += aux
            time_awb.add_value(aux)
            logging.debug("AWB Match delay: %s ms", str(round((time.time() - curtime) * 1000, 1)))
    else:
        time_awb.add_value(0)

    if PiCam2PreviewEnabled:
        if mode == 'still':
            camera.switch_mode_and_capture_file(capture_config,
                                                StillFrameFilenamePattern % (CurrentFrame, CurrentStill))
            CurrentStill += 1
        else:
            # This one should not happen, will not allow PiCam2 scan in preview mode
            camera.switch_mode_and_capture_file(capture_config, FrameFilenamePattern % CurrentFrame)
    else:
        time.sleep(
            stabilization_delay_value.get() / 1000)  # Allow time to stabilize image, it can get too fast with PiCamera2
        if mode == 'still':
            captured_image = camera.capture_image("main")
            captured_image.save(StillFrameFilenamePattern % (CurrentFrame, CurrentStill))
            CurrentStill += 1
        else:
            if HdrCaptureActive:
                # Stabilization delay for HDR managed inside capture_hdr
                capture_hdr(mode)
            else:
                capture_single(mode)

    SessionData["CurrentDate"] = str(datetime.now())
    SessionData["CurrentFrame"] = str(CurrentFrame)


def start_scan_simulated():
    global ScanOngoing
    global CurrentScanStartFrame, CurrentScanStartTime
    global simulated_captured_frame_list, simulated_images_in_list
    global ScanStopRequested
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time
    global total_wait_time_save_image
    global session_frames
    global last_frame_time

    if ScanOngoing:
        ScanStopRequested = True  # Ending the scan process will be handled in the next (or ongoing) capture loop
    else:
        if BaseDir == CurrentDir:
            tk.messagebox.showerror("Error!",
                                    "Please specify a folder where to retrieve captured images for "
                                    "scan simulation.")
            return

        Start_btn.config(text="STOP Scan", bg='red', fg='white', relief=SUNKEN)
        SessionData["CurrentDate"] = str(datetime.now())
        SessionData["CurrentDir"] = CurrentDir
        SessionData["CurrentFrame"] = str(CurrentFrame)
        CurrentScanStartTime = datetime.now()
        CurrentScanStartFrame = CurrentFrame

        ScanOngoing = True
        arrange_custom_spinboxes_status(win)
        last_frame_time = time.time() + 3

        # Enable/Disable related buttons
        button_status_change_except(Start_btn, ScanOngoing)

        # Reset time counters
        total_wait_time_save_image = 0
        total_wait_time_preview_display = 0
        total_wait_time_awb = 0
        total_wait_time_autoexp = 0
        session_start_time = time.time()
        session_frames = 0

        # Get list of previously captured frames for scan simulation
        if not os.path.isdir(CurrentDir):
            tk.messagebox.showerror("Error!", "Folder " + CurrentDir + " does not  exist!")
        else:
            simulated_captured_frame_list = os.listdir(CurrentDir)
            simulated_captured_frame_list.sort()
            simulated_images_in_list = len(simulated_captured_frame_list)
            # Invoke capture_loop  a first time shen scan starts
            win.after(500, capture_loop_simulated)


def stop_scan_simulated():
    global ScanOngoing

    Start_btn.config(text="START Scan", bg=save_bg, fg=save_fg, relief=RAISED)

    ScanOngoing = False
    arrange_custom_spinboxes_status(win)

    # Enable/Disable related buttons
    button_status_change_except(Start_btn, ScanOngoing)


def capture_loop_simulated():
    global CurrentFrame
    global FramesPerMinute, FramesToGo
    global simulated_capture_image
    global session_frames
    global disk_space_error_to_notify
    global ScanStopRequested

    if ScanStopRequested:
        stop_scan_simulated()
        ScanStopRequested = False
        curtime = time.time()
        logging.debug("Total session time: %s seg for %i frames (%i ms per frame)",
                      str(round((curtime - session_start_time), 1)),
                      session_frames,
                      round(((curtime - session_start_time) * 1000 / session_frames), 1))
        logging.debug("Total time to save images: %s seg, (%i ms per frame)",
                      str(round((total_wait_time_save_image), 1)),
                      round((total_wait_time_save_image * 1000 / session_frames), 1))
        logging.debug("Total time to display preview image: %s seg, (%i ms per frame)",
                      str(round((total_wait_time_preview_display), 1)),
                      round((total_wait_time_preview_display * 1000 / session_frames), 1))
        logging.debug("Total time waiting for AWB adjustment: %s seg, (%i ms per frame)",
                      str(round((total_wait_time_awb), 1)),
                      round((total_wait_time_awb * 1000 / session_frames), 1))
        logging.debug("Total time waiting for AE adjustment: %s seg, (%i ms per frame)",
                      str(round((total_wait_time_autoexp), 1)),
                      round((total_wait_time_autoexp * 1000 / session_frames), 1))
        if disk_space_error_to_notify:
            tk.messagebox.showwarning("Disk space low",
                                      f"Running out of disk space, only {int(available_space_mb)} MB remain. "
                                      "Please delete some files before continuing current scan.")
            disk_space_error_to_notify = False
    if ScanOngoing:
        os.chdir(CurrentDir)
        frame_to_display = CurrentFrame % simulated_images_in_list
        filename, ext = os.path.splitext(simulated_captured_frame_list[frame_to_display])
        if ext == '.jpg':
            simulated_capture_image = Image.open(simulated_captured_frame_list[frame_to_display])
            if negative_image.get():
                simulated_capture_image = reverse_image(simulated_capture_image)
            draw_preview_image(simulated_capture_image, CurrentFrame, 0)

        # Update remaining time
        aux = frames_to_go_str.get()
        if aux.isdigit() and time.time() > frames_to_go_key_press_time:
            FramesToGo = int(aux)
            if FramesToGo > 0:
                FramesToGo -= 1
                frames_to_go_str.set(str(FramesToGo))
                SessionData["FramesToGo"] = FramesToGo
                if FramesPerMinute != 0:
                    minutes_pending = FramesToGo // FramesPerMinute
                    time_to_go_str.set(f"Time to go: {(minutes_pending // 60):02} h, {(minutes_pending % 60):02} m")

        CurrentFrame += 1
        session_frames += 1
        register_frame()
        SessionData["CurrentFrame"] = str(CurrentFrame)

        # Update number of captured frames
        Scanned_Images_number_str.set(str(CurrentFrame))
        # Update film time
        fps = 18 if SessionData["FilmType"] == "S8" else 16
        film_time = f"Film time: {(CurrentFrame // fps) // 60:02}:{(CurrentFrame // fps) % 60:02}"
        Scanned_Images_time_str.set(film_time)
        # Update Frames per Minute
        scan_period_frames = CurrentFrame - CurrentScanStartFrame
        if FPM_CalculatedValue == -1:  # FPM not calculated yet, display some indication
            aux_str = ''.join([char * int(min(5, scan_period_frames)) for char in '.'])
            Scanned_Images_Fpm_str.set(f"Frames/Min: {aux_str}")
        else:
            FramesPerMinute = FPM_CalculatedValue
            Scanned_Images_Fpm_str.set(f"Frames/Min: {FramesPerMinute}")

        # Invoke capture_loop one more time, as long as scan is ongoing
        win.after(500, capture_loop_simulated)

        # display rolling averages
        time_save_image_value.set(
            int(time_save_image.get_average() * 1000) if time_save_image.get_average() is not None else 0)
        time_preview_display_value.set(
            int(time_preview_display.get_average() * 1000) if time_preview_display.get_average() is not None else 0)
        time_awb_value.set(int(time_awb.get_average() * 1000) if time_awb.get_average() is not None else 0)
        time_autoexp_value.set(int(time_autoexp.get_average() * 1000) if time_autoexp.get_average() is not None else 0)

        if session_frames % 50 == 0 and not disk_space_available():  # Only every 50 frames (500MB buffer exist)
            logging.error("No disk space available, stopping scan process.")
            if ScanOngoing:
                ScanStopRequested = True  # Stop in next capture loop


def start_scan():
    global ScanOngoing
    global CurrentScanStartFrame, CurrentScanStartTime
    global ScanStopRequested
    global NewFrameAvailable
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time
    global total_wait_time_save_image
    global session_frames
    global last_frame_time

    if ScanOngoing:
        ScanStopRequested = True  # Ending the scan process will be handled in the next (or ongoing) capture loop
    else:
        if BaseDir == CurrentDir or not os.path.isdir(CurrentDir):
            tk.messagebox.showerror("Error!", "Please specify a folder where to store the "
                                              "captured images.")
            return

        Start_btn.config(text="STOP Scan", bg='red', fg='white', relief=SUNKEN)
        SessionData["CurrentDate"] = str(datetime.now())
        SessionData["CurrentDir"] = CurrentDir
        SessionData["CurrentFrame"] = str(CurrentFrame)
        CurrentScanStartTime = datetime.now()
        CurrentScanStartFrame = CurrentFrame

        is_dng = file_type_dropdown_selected.get() == 'dng'
        is_png = file_type_dropdown_selected.get() == 'png'
        if (is_dng or is_png) and negative_image.get():  # Incompatible choices, display error and quit
            tk.messagebox.showerror("Error!",
                                    "Cannot scan negative images to DNG or PNG files. "
                                    "Please correct and retry.")
            logging.debug("Cannot scan negative images to DNG file. Please correct and retry.")
            return

        ScanOngoing = True
        arrange_custom_spinboxes_status(win)
        last_frame_time = time.time() + 3

        # Set new frame indicator to false, in case this is the cause of the strange
        # behaviour after stopping/restarting the scan process
        NewFrameAvailable = False

        # Enable/Disable related buttons
        button_status_change_except(Start_btn, ScanOngoing)

        # Reset time counters
        total_wait_time_save_image = 0
        total_wait_time_preview_display = 0
        total_wait_time_awb = 0
        total_wait_time_autoexp = 0
        session_start_time = time.time()
        session_frames = 0

        # Send command to Arduino to start scan (as applicable, Arduino keeps its own status)
        if not SimulatedRun:
            send_arduino_command(CMD_START_SCAN)

        # Invoke capture_loop a first time when scan starts
        win.after(5, capture_loop)


def stop_scan():
    global ScanOngoing

    if ScanOngoing:  # Scanner session to be stopped
        Start_btn.config(text="START Scan", bg=save_bg, fg=save_fg, relief=RAISED)

    ScanOngoing = False
    arrange_custom_spinboxes_status(win)

    # Send command to Arduino to stop scan (as applicable, Arduino keeps its own status)
    if not SimulatedRun:
        logging.debug("Sending CMD_STOP_SCAN")
        send_arduino_command(CMD_STOP_SCAN)

    # Enable/Disable related buttons
    button_status_change_except(Start_btn, ScanOngoing)


def capture_loop():
    global CurrentFrame
    global FramesPerMinute, FramesToGo
    global NewFrameAvailable
    global ScanProcessError, ScanProcessError_LastTime
    global ScanStopRequested
    global session_frames, CurrentStill
    global disk_space_error_to_notify

    if ScanStopRequested:
        stop_scan()
        ScanStopRequested = False
        curtime = time.time()
        if session_frames > 0:
            logging.debug("Total session time: %s seg for %i frames (%i ms per frame)",
                          str(round((curtime - session_start_time), 1)),
                          session_frames,
                          round(((curtime - session_start_time) * 1000 / session_frames), 1))
            logging.debug("Total time to save images: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_save_image), 1)),
                          round((total_wait_time_save_image * 1000 / session_frames), 1))
            logging.debug("Total time to display preview image: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_preview_display), 1)),
                          round((total_wait_time_preview_display * 1000 / session_frames), 1))
            logging.debug("Total time waiting for AWB adjustment: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_awb), 1)),
                          round((total_wait_time_awb * 1000 / session_frames), 1))
            logging.debug("Total time waiting for AE adjustment: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_autoexp), 1)),
                          round((total_wait_time_autoexp * 1000 / session_frames), 1))
        if disk_space_error_to_notify:
            tk.messagebox.showwarning("Disk space low",
                                      f"Running out of disk space, only {int(available_space_mb)} MB remain. "
                                      "Please delete some files before continuing current scan.")
            disk_space_error_to_notify = False
    elif ScanOngoing:
        if NewFrameAvailable:
            # Update remaining time
            aux = frames_to_go_str.get()
            if aux.isdigit() and time.time() > frames_to_go_key_press_time:
                FramesToGo = int(aux)
                if FramesToGo > 0:
                    FramesToGo -= 1
                    frames_to_go_str.set(str(FramesToGo))
                    SessionData["FramesToGo"] = FramesToGo
                    if FramesPerMinute != 0:
                        minutes_pending = FramesToGo // FramesPerMinute
                        time_to_go_str.set(f"Time to go: {(minutes_pending // 60):02} h, {(minutes_pending % 60):02} m")
                else:
                    ScanStopRequested = True  # Stop in next capture loop
                    SessionData["FramesToGo"] = -1
                    frames_to_go_str.set('')  # clear frames to go box to prevent it stops again in next scan
            CurrentFrame += 1
            session_frames += 1
            register_frame()
            CurrentStill = 1
            capture('normal')
            if not SimulatedRun:
                try:
                    # Set NewFrameAvailable to False here, to avoid overwriting new frame from arduino
                    NewFrameAvailable = False
                    logging.debug("Frame %i captured.", CurrentFrame)
                    send_arduino_command(CMD_GET_NEXT_FRAME)  # Tell Arduino to move to next frame
                except IOError:
                    CurrentFrame -= 1
                    NewFrameAvailable = True  # Set NewFrameAvailable to True to repeat next time
                    # Log error to console
                    logging.warning("Error while telling Arduino to move to next Frame.")
                    logging.warning("Frame %i capture to be tried again.", CurrentFrame)
                    win.after(5, capture_loop)
                    return

            SessionData["CurrentDate"] = str(datetime.now())
            SessionData["CurrentDir"] = CurrentDir
            SessionData["CurrentFrame"] = str(CurrentFrame)
            # with open(PersistedDataFilename, 'w') as f:
            #     json.dump(SessionData, f)

            # Update number of captured frames
            Scanned_Images_number_str.set(str(CurrentFrame))
            # Update film time
            fps = 18 if SessionData["FilmType"] == "S8" else 16
            film_time = f"Film time: {(CurrentFrame // fps) // 60:02}:{(CurrentFrame // fps) % 60:02}"
            Scanned_Images_time_str.set(film_time)
            # Update Frames per Minute
            scan_period_frames = CurrentFrame - CurrentScanStartFrame
            if FPM_CalculatedValue == -1:  # FPM not calculated yet, display some indication
                aux_str = ''.join([char * int(min(5, scan_period_frames)) for char in '.'])
                Scanned_Images_Fpm_str.set(f"Frames/Min: {aux_str}")
            else:
                FramesPerMinute = FPM_CalculatedValue
                Scanned_Images_Fpm_str.set(f"Frames/Min: {FPM_CalculatedValue}")
            if session_frames % 50 == 0 and not disk_space_available():  # Only every 50 frames (500MB buffer exist)
                logging.error("No disk space available, stopping scan process.")
                if ScanOngoing:
                    ScanStopRequested = True  # Stop in next capture loop
        elif ScanProcessError:
            if ScanProcessError_LastTime != 0:
                if time.time() - ScanProcessError_LastTime <= 5:  # Second error in less than 5 seconds: Stop
                    curtime = time.ctime()
                    logging.error("Too many errors during scan process, stopping.")
                    ScanProcessError = False
                    if ScanOngoing:
                        ScanStopRequested = True  # Stop in next capture loop
            ScanProcessError_LastTime = time.time()
            ScanProcessError = False
            if not ScanStopRequested:
                NewFrameAvailable = True  # Simulate new frame to continue scan
                logging.warning(
                    f"Error during scan process, frame {CurrentFrame}, simulating new frame. Maybe misaligned.")

        # display rolling averages
        if ExperimentalMode:
            time_save_image_value.set(
                int(time_save_image.get_average() * 1000) if time_save_image.get_average() is not None else 0)
            time_preview_display_value.set(
                int(time_preview_display.get_average() * 1000) if time_preview_display.get_average() is not None else 0)
            time_awb_value.set(int(time_awb.get_average() * 1000) if time_awb.get_average() is not None else 0)
            time_autoexp_value.set(
                int(time_autoexp.get_average() * 1000) if time_autoexp.get_average() is not None else 0)

        # Invoke capture_loop one more time, as long as scan is ongoing
        win.after(5, capture_loop)


def temp_in_fahrenheit_selection():
    SessionData["TempInFahrenheit"] = str(temp_in_fahrenheit.get())


def temperature_check():
    global last_temp
    global LastTempInFahrenheit

    update_rpi_temp()
    if last_temp != RPiTemp or LastTempInFahrenheit != temp_in_fahrenheit.get():
        if temp_in_fahrenheit.get():
            rounded_temp = round(RPiTemp * 1.8 + 32, 1)
            temp_str = str(rounded_temp) + 'ºF'
        else:
            rounded_temp = round(RPiTemp, 1)
            temp_str = str(rounded_temp) + 'º'
        RPi_temp_value_label.config(text=str(temp_str))
        last_temp = RPiTemp
        LastTempInFahrenheit = temp_in_fahrenheit.get()


def frames_to_go_key_press(event):
    global frames_to_go_key_press_time
    # Block keyboard entry if the flag is set
    if event.keysym not in {'1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
                            'KP_1', 'KP_2', 'KP_3', 'KP_4', 'KP_5', 'KP_6', 'KP_7', 'KP_8', 'KP_9', 'KP_0',
                            'Delete', 'BackSpace', 'Left', 'Right'}:
        return "break"
    else:
        frames_to_go_key_press_time = time.time() + 5  # 5 sec guard time to allow typing entire number


def preview_check():
    if SimulatedRun or CameraDisabled:
        return

    if real_time_display.get() and not camera._preview:
        real_time_display.set(False)
        set_real_time_display()


def onesec_periodic_checks():  # Update RPi temperature every 10 seconds
    global onesec_after

    temperature_check()
    preview_check()

    if not ExitingApp:
        onesec_after = win.after(1000, onesec_periodic_checks)


def set_file_type(event):
    SessionData["FileType"] = file_type_dropdown_selected.get()


def set_resolution(event):
    global max_inactivity_delay
    SessionData["CaptureResolution"] = resolution_dropdown_selected.get()
    camera_resolutions.set_active(resolution_dropdown_selected.get())
    if resolution_dropdown_selected.get() == "4056x3040":
        max_inactivity_delay = reference_inactivity_delay * 2
    else:
        max_inactivity_delay = reference_inactivity_delay
    send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
    logging.debug(f"Set max_inactivity_delay as {max_inactivity_delay}")

    PiCam2_change_resolution()


def UpdatePlotterWindow(PTValue, ThresholdLevel):
    global MaxPT, MinPT, PrevPTValue, PrevThresholdLevel

    if plotter_canvas == None:
        logging.error("Plotter canvas does not exist, exiting...")
        return

    if PTValue > MaxPT * 10:
        logging.warning("PT level too high, ignoring it")
        return

    MaxPT = max(MaxPT, PTValue)
    MinPT = min(MinPT, PTValue)
    plotter_canvas.create_text(10, 5, text=str(MaxPT), anchor='nw', font=f"Helvetica {8}")
    plotter_canvas.create_text(10, plotter_height - 15, text=str(MinPT), anchor='nw', font=f"Helvetica {8}")
    # Shift the graph to the left
    for item in plotter_canvas.find_all():
        plotter_canvas.move(item, -5, 0)

    usable_height = plotter_height - 15
    # Delete lines moving out of the canvas
    for item in plotter_canvas.find_overlapping(-10, 0, 0, usable_height):
        plotter_canvas.delete(item)

    # Draw the new line segment for PT Level
    plotter_canvas.create_line(plotter_width - 6, 15 + usable_height - (PrevPTValue / (MaxPT / usable_height)),
                               plotter_width - 1, 15 + usable_height - (PTValue / (MaxPT / usable_height)), width=1,
                               fill="blue")
    # Draw the new line segment for threshold
    if (ThresholdLevel > MaxPT):
        logging.debug(f"ThresholdLevel value is wrong ({ThresholdLevel}), replacing by previous ({PrevThresholdLevel})")
        # Swap by previous if bigger than MaxPT, sometimes I2C losses second parameter, no idea why
        ThresholdLevel = PrevThresholdLevel
    plotter_canvas.create_line(plotter_width - 6, 15 + usable_height - (PrevThresholdLevel / (MaxPT / usable_height)),
                               plotter_width - 1, 15 + usable_height - (ThresholdLevel / (MaxPT / usable_height)),
                               width=1, fill="red")
    PrevPTValue = PTValue
    PrevThresholdLevel = ThresholdLevel
    if MaxPT > 100:  # Do not allow below 100
        MaxPT -= 1  # Dynamic max
    if MinPT < 800:  # Do not allow above 800
        MinPT += 1  # Dynamic min


# send_arduino_command: No response expected
def send_arduino_command(cmd, param=0):
    if not SimulatedRun:
        time.sleep(0.0001)  # wait 100 µs, to avoid I/O errors
        try:
            i2c.write_i2c_block_data(16, cmd, [int(param % 256), int(param >> 8)])  # Send command to Arduino
        except IOError:
            logging.warning(
                f"Error while sending command {cmd} (param {param}) to Arduino while handling frame {CurrentFrame}. "
                f"Retrying...")
            time.sleep(0.2)  # wait 100 µs, to avoid I/O errors
            i2c.write_i2c_block_data(16, cmd, [int(param % 256), int(param >> 8)])  # Send command to Arduino

        time.sleep(0.0001)  # wait 100 µs, same


def arduino_listen_loop():  # Waits for Arduino communicated events and dispatches accordingly
    global NewFrameAvailable
    global RewindErrorOutstanding, RewindEndOutstanding
    global FastForwardErrorOutstanding, FastForwardEndOutstanding
    global ArduinoTrigger
    global ScanProcessError
    global last_frame_time
    global Controller_Id
    global ScanStopRequested
    global arduino_after

    if not SimulatedRun:
        try:
            ArduinoData = i2c.read_i2c_block_data(16, CMD_GET_CNT_STATUS, 5)
            ArduinoTrigger = ArduinoData[0]
            ArduinoParam1 = ArduinoData[1] * 256 + ArduinoData[2]
            ArduinoParam2 = ArduinoData[3] * 256 + ArduinoData[
                4]  # Sometimes this part arrives as 255, 255, no idea why
        except IOError as e:
            ArduinoTrigger = 0
            # Log error to console
            # When error is 121, not really an error, means Arduino has nothing to data available for us
            if e.errno != 121:
                logging.warning(
                    f"Non-critical IOError ({e}) while checking incoming event from Arduino. Will check again.")

    if ScanOngoing and time.time() > last_frame_time:
        # If scan is ongoing, and more than 3 seconds have passed since last command, maybe one
        # command from/to Arduino (frame received/go to next frame) has been lost.
        # In such case, we force a 'fake' new frame command to allow process to continue
        # This means a duplicate frame might be generated.
        last_frame_time = time.time() + int(
            max_inactivity_delay * 0.34)  # Delay shared with arduino, 1/3rd less to avoid conflict with end reel
        NewFrameAvailable = True
        logging.warning("More than %i sec. since last command: Forcing new "
                        "frame event (frame %i).", int(max_inactivity_delay * 0.34), CurrentFrame)

    if ArduinoTrigger == 0:  # Do nothing
        pass
    elif ArduinoTrigger == RSP_VERSION_ID:  # New Frame available
        Controller_Id = ArduinoParam1
        if Controller_Id == 1:
            logging.info("Arduino controller detected")
        elif Controller_Id == 2:
            logging.info("Raspberry Pi Pico controller detected")
    elif ArduinoTrigger == RSP_FORCE_INIT:  # Controller reloaded, sent init sequence again
        logging.debug("Controller requested to reinit")
        reinit_controller()
    elif ArduinoTrigger == RSP_FRAME_AVAILABLE:  # New Frame available
        # Delay shared with arduino, 2 seconds less to avoid conflict with end reel
        last_frame_time = time.time() + max_inactivity_delay - 2
        NewFrameAvailable = True
    elif ArduinoTrigger == RSP_SCAN_ERROR:  # Error during scan
        logging.warning("Received scan error from Arduino (%i, %i)", ArduinoParam1, ArduinoParam2)
        ScanProcessError = True
    elif ArduinoTrigger == RSP_SCAN_ENDED:  # Scan arrived at the end of the reel
        logging.warning("End of reel reached: Scan terminated")
        ScanStopRequested = True
    elif ArduinoTrigger == RSP_REPORT_AUTO_LEVELS:  # Get auto levels from Arduino, to be displayed in UI, if auto on
        if ExpertMode:
            if (auto_pt_level_enabled.get()):
                pt_level_value.set(ArduinoParam1)
            if (auto_framesteps_enabled.get()):
                steps_per_frame_value.set(ArduinoParam2)
    elif ArduinoTrigger == RSP_REWIND_ENDED:  # Rewind ended, we can re-enable buttons
        RewindEndOutstanding = True
        logging.debug("Received rewind end event from Arduino")
    elif ArduinoTrigger == RSP_FAST_FORWARD_ENDED:  # FastForward ended, we can re-enable buttons
        FastForwardEndOutstanding = True
        logging.debug("Received fast forward end event from Arduino")
    elif ArduinoTrigger == RSP_REWIND_ERROR:  # Error during Rewind
        RewindErrorOutstanding = True
        logging.warning("Received rewind error from Arduino")
    elif ArduinoTrigger == RSP_FAST_FORWARD_ERROR:  # Error during FastForward
        FastForwardErrorOutstanding = True
        logging.warning("Received fast forward error from Arduino")
    elif ArduinoTrigger == RSP_REPORT_PLOTTER_INFO:  # Integrated plotter info
        if PlotterMode:
            UpdatePlotterWindow(ArduinoParam1, ArduinoParam2)
    elif ArduinoTrigger == RSP_FILM_FORWARD_ENDED:
        logging.warning("Received film forward end from Arduino")
        advance_movie(True)
    else:
        logging.warning("Unrecognized incoming event (%i) from Arduino.", ArduinoTrigger)

    if ArduinoTrigger != 0:
        ArduinoTrigger = 0

    if not ExitingApp:
        arduino_after = win.after(10, arduino_listen_loop)


def load_persisted_data_from_disk():
    global SessionData
    global PersistedDataLoaded

    # Check if persisted data file exist: If it does, load it
    if os.path.isfile(PersistedDataFilename):
        persisted_data_file = open(PersistedDataFilename)
        SessionData = json.load(persisted_data_file)
        persisted_data_file.close()
        PersistedDataLoaded = True


def load_config_data():
    for item in SessionData:
        logging.debug("%s=%s", item, str(SessionData[item]))
    if PersistedDataLoaded:
        logging.debug("SessionData loaded from disk:")
        if 'TempInFahrenheit' in SessionData:
            temp_in_fahrenheit.set(eval(SessionData["TempInFahrenheit"]))
            if temp_in_fahrenheit.get():
                temp_in_fahrenheit_checkbox.select()
        if ExpertMode:
            if 'MatchWaitMargin' in SessionData:
                aux = int(SessionData["MatchWaitMargin"])
                match_wait_margin_value.set(aux)
            else:
                match_wait_margin_value.set(50)
            if 'CaptureStabilizationDelay' in SessionData:
                aux = float(SessionData["CaptureStabilizationDelay"])
                stabilization_delay_value.set(round(aux * 1000))
            else:
                stabilization_delay_value.set(100)


def arrange_widget_state(disabled, widget_list):
    for widget in widget_list:
        if isinstance(widget, tk.Spinbox):
            widget.config(state='readonly' if disabled else NORMAL)  # Used to be readonly instead of disabled
        elif isinstance(widget, tk.OptionMenu) or isinstance(widget, tk.Label) or isinstance(widget, tk.Checkbutton):
            widget.config(state=DISABLED if disabled else NORMAL)
        elif isinstance(widget, tk.Checkbutton):
            if disabled:
                widget.select()
            else:
                widget.deselect()


def arrange_custom_spinboxes_status(widget):
    widgets = widget.winfo_children()
    for widget in widgets:
        if isinstance(widget, DynamicSpinbox):
            widget.set_custom_state('block_kbd_entry' if ScanOngoing else 'normal')
        elif isinstance(widget, tk.Frame) or isinstance(widget, tk.LabelFrame):
            arrange_custom_spinboxes_status(widget)


def load_session_data():
    global CurrentDir
    global CurrentFrame, FramesToGo
    global MinFrameStepsS8, MinFrameStepsR8
    global PTLevelS8, PTLevelR8
    global HdrCaptureActive
    global HdrViewX4Active
    global max_inactivity_delay
    global manual_wb_red_value, manual_wb_blue_value

    if PersistedDataLoaded:
        confirm = tk.messagebox.askyesno(title='Persisted session data exist',
                                         message='ALT-Scann 8 was interrupted during the last session.\
                                         \r\nDo you want to continue from where it was stopped?')
        if confirm:
            logging.debug("SessionData loaded from disk:")
            if 'CurrentDir' in SessionData:
                CurrentDir = SessionData["CurrentDir"]
                # If directory in configuration does not exist we set the current working dir
                if not os.path.isdir(CurrentDir):
                    CurrentDir = os.getcwd()
                folder_frame_target_dir.config(text=CurrentDir)
            if 'CurrentFrame' in SessionData:
                CurrentFrame = int(SessionData["CurrentFrame"])
                Scanned_Images_number_str.set(SessionData["CurrentFrame"])
            if 'FramesToGo' in SessionData:
                if SessionData["FramesToGo"] != -1:
                    FramesToGo = int(SessionData["FramesToGo"])
                    frames_to_go_str.set(str(FramesToGo))
            if 'FilmType' in SessionData:
                film_type.set(SessionData["FilmType"])
                if SessionData["FilmType"] == "R8":
                    set_r8()
                elif SessionData["FilmType"] == "S8":
                    set_s8()
            if 'FileType' in SessionData:
                file_type_dropdown_selected.set(SessionData["FileType"])
            if 'CaptureResolution' in SessionData:
                valid_resolution_list = camera_resolutions.get_list()
                selected_resolution = SessionData["CaptureResolution"]
                if selected_resolution not in valid_resolution_list:
                    if selected_resolution + ' *' in valid_resolution_list:
                        selected_resolution = selected_resolution + ' *'
                    else:
                        selected_resolution = valid_resolution_list[0]
                resolution_dropdown_selected.set(selected_resolution)
                if resolution_dropdown_selected.get() == "4056x3040":
                    max_inactivity_delay = reference_inactivity_delay * 2
                else:
                    max_inactivity_delay = reference_inactivity_delay
                send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
                logging.debug(f"max_inactivity_delay: {max_inactivity_delay}")
                PiCam2_change_resolution()
            if 'NegativeCaptureActive' in SessionData:
                negative_image.set(SessionData["NegativeCaptureActive"])
                set_negative_image()
            if 'AutoStopType' in SessionData:
                autostop_type.set(SessionData["AutoStopType"])
            if 'AutoStopActive' in SessionData:
                auto_stop_enabled.set(SessionData["AutoStopActive"])
                set_auto_stop_enabled()
            if ExperimentalMode:
                if 'HdrCaptureActive' in SessionData:
                    HdrCaptureActive = eval(SessionData["HdrCaptureActive"])
                    hdr_set_controls()
                    if HdrCaptureActive:
                        max_inactivity_delay = reference_inactivity_delay * 2
                        send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
                        logging.debug(f"max_inactivity_delay: {max_inactivity_delay}")
                        hdr_capture_active_checkbox.select()
                if 'HdrViewX4Active' in SessionData:
                    HdrViewX4Active = eval(SessionData["HdrViewX4Active"])
                    if HdrViewX4Active:
                        hdr_viewx4_active_checkbox.select()
                    else:
                        hdr_viewx4_active_checkbox.deselect()
                if 'HdrMinExp' in SessionData:
                    aux = int(SessionData["HdrMinExp"])
                    hdr_min_exp_value.set(aux)
                else:
                    hdr_min_exp_value.set(hdr_lower_exp)
                if 'HdrMaxExp' in SessionData:
                    aux = int(SessionData["HdrMaxExp"])
                    hdr_max_exp_value.set(aux)
                else:
                    hdr_max_exp_value.set(hdr_higher_exp)
                if 'HdrBracketAuto' in SessionData:
                    hdr_bracket_auto.set(SessionData["HdrBracketAuto"])
                else:
                    hdr_bracket_auto.set(hdr_higher_exp - hdr_lower_exp)
                if 'HdrMergeInPlace' in SessionData:
                    hdr_merge_in_place.set(SessionData["HdrMergeInPlace"])
                if 'HdrBracketWidth' in SessionData:
                    aux = int(SessionData["HdrBracketWidth"])
                    hdr_bracket_width_value.set(aux)
                if 'HdrBracketShift' in SessionData:
                    aux = SessionData["HdrBracketShift"]
                    hdr_bracket_shift_value.set(aux)
            if ExpertMode:
                if 'CurrentExposure' in SessionData:
                    aux = SessionData["CurrentExposure"]
                    if isinstance(aux, str) and (aux == "Auto" or aux == "0") or isinstance(aux, int) and aux == 0:
                        aux = 0
                        AE_enabled.set(True)
                        set_auto_exposure()
                        auto_exposure_wait_btn.config(state=NORMAL)
                    else:
                        if isinstance(aux, str):
                            aux = int(float(aux))
                        AE_enabled.set(False)
                        auto_exposure_wait_btn.config(state=DISABLED)
                    if not SimulatedRun and not CameraDisabled:
                        camera.controls.ExposureTime = int(aux)
                        camera.set_controls({"AeEnable": AE_enabled.get()})
                    exposure_value.set(aux / 1000)
                if 'ExposureAdaptPause' in SessionData:
                    if isinstance(SessionData["ExposureAdaptPause"], bool):
                        aux = SessionData["ExposureAdaptPause"]
                    else:
                        aux = eval(SessionData["ExposureAdaptPause"])
                    auto_exposure_change_pause.set(aux)
                    auto_exposure_wait_btn.config(state=NORMAL if exposure_value.get() == 0 else DISABLED)
                if 'CurrentAwbAuto' in SessionData:
                    if isinstance(SessionData["CurrentAwbAuto"], bool):
                        AWB_enabled.set(SessionData["CurrentAwbAuto"])
                    else:
                        AWB_enabled.set(eval(SessionData["CurrentAwbAuto"]))
                    wb_blue_spinbox.config(state='readonly' if AWB_enabled.get() else NORMAL)
                    wb_red_spinbox.config(state='readonly' if AWB_enabled.get() else NORMAL)
                    auto_wb_wait_btn.config(state=NORMAL if AWB_enabled.get() else DISABLED)
                    if not SimulatedRun and not CameraDisabled:
                        camera.set_controls({"AwbEnable": AWB_enabled.get()})
                    arrange_widget_state(not AWB_enabled.get(), [auto_wb_wait_btn])
                    arrange_widget_state(AWB_enabled.get(), [wb_red_spinbox, wb_blue_spinbox])
                if 'AwbPause' in SessionData:
                    if isinstance(SessionData["CurrentAwbAuto"], bool):
                        aux = SessionData["AwbPause"]
                    else:
                        aux = eval(SessionData["AwbPause"])
                    if aux:
                        auto_wb_wait_btn.select()
                    else:
                        auto_wb_wait_btn.deselect()
                if 'GainRed' in SessionData:
                    aux = float(SessionData["GainRed"])
                    wb_red_value.set(round(aux, 1))
                    manual_wb_red_value = aux
                if 'GainBlue' in SessionData:
                    aux = float(SessionData["GainBlue"])
                    wb_blue_value.set(round(aux, 1))
                    manual_wb_blue_value = aux
                # Recover miscellaneous PiCamera2 controls
                if "AeConstraintMode" in SessionData:
                    aux = SessionData["AeConstraintMode"]
                    AeConstraintMode_dropdown_selected.set(aux)
                    if not SimulatedRun and not CameraDisabled:
                        camera.set_controls({"AeConstraintMode": AeConstraintMode_dict[aux]})
                if "AeMeteringMode" in SessionData:
                    aux = SessionData["AeMeteringMode"]
                    AeMeteringMode_dropdown_selected.set(aux)
                    if not SimulatedRun and not CameraDisabled:
                        camera.set_controls({"AeMeteringMode": AeMeteringMode_dict[aux]})
                if "AeExposureMode" in SessionData:
                    aux = SessionData["AeExposureMode"]
                    AeExposureMode_dropdown_selected.set(aux)
                    if not SimulatedRun and not CameraDisabled:
                        camera.set_controls({"AeExposureMode": AeExposureMode_dict[aux]})
                if "AwbMode" in SessionData:
                    aux = SessionData["AwbMode"]
                    AwbMode_dropdown_selected.set(aux)
                    if not SimulatedRun and not CameraDisabled:
                        camera.set_controls({"AwbMode": AwbMode_dict[aux]})
                # Recover frame alignment values
                if 'MinFrameSteps' in SessionData:
                    MinFrameSteps = int(SessionData["MinFrameSteps"])
                    steps_per_frame_value.set(MinFrameSteps)
                    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, MinFrameSteps)
                if 'FrameStepsAuto' in SessionData:
                    auto_framesteps_enabled.set(SessionData["FrameStepsAuto"])
                    steps_per_frame_auto()
                    if auto_framesteps_enabled.get():
                        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0)
                    else:
                        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, steps_per_frame_value.get())
                if 'MinFrameStepsS8' in SessionData:
                    MinFrameStepsS8 = SessionData["MinFrameStepsS8"]
                if 'MinFrameStepsR8' in SessionData:
                    MinFrameStepsR8 = SessionData["MinFrameStepsR8"]
                if 'FrameFineTune' in SessionData:
                    aux = SessionData["FrameFineTune"]
                    frame_fine_tune_value.set(aux)
                    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, aux)
                if 'FrameExtraSteps' in SessionData:
                    aux = SessionData["FrameExtraSteps"]
                    aux = min(aux, 20)
                    frame_extra_steps_value.set(aux)
                    send_arduino_command(CMD_SET_EXTRA_STEPS, aux)
                if 'PTLevelAuto' in SessionData:
                    auto_pt_level_enabled.set(SessionData["PTLevelAuto"])
                    set_auto_pt_level()
                    if auto_pt_level_enabled.get():
                        send_arduino_command(CMD_SET_PT_LEVEL, 0)
                    else:
                        send_arduino_command(CMD_SET_PT_LEVEL, pt_level_value.get())
                if 'PTLevel' in SessionData:
                    PTLevel = int(SessionData["PTLevel"])
                    pt_level_value.set(PTLevel)
                    if not auto_pt_level_enabled.get():
                        send_arduino_command(CMD_SET_PT_LEVEL, PTLevel)
                if 'PTLevelS8' in SessionData:
                    PTLevelS8 = SessionData["PTLevelS8"]
                if 'PTLevelR8' in SessionData:
                    PTLevelR8 = SessionData["PTLevelR8"]
                if 'ScanSpeed' in SessionData:
                    aux = int(SessionData["ScanSpeed"])
                    scan_speed_value.set(aux)
                    send_arduino_command(CMD_SET_SCAN_SPEED, aux)
                if 'PreviewModule' in SessionData:
                    aux = int(SessionData["PreviewModule"])
                    preview_module_value.set(aux)
                if 'Brightness' in SessionData:
                    aux = SessionData["Brightness"]
                    brightness_value.set(aux)
                    if not SimulatedRun and not CameraDisabled:
                        camera.set_controls({"Brightness": aux})
                if 'Contrast' in SessionData:
                    aux = SessionData["Contrast"]
                    contrast_value.set(aux)
                    if not SimulatedRun and not CameraDisabled:
                        camera.set_controls({"Contrast": aux})
                if 'Saturation' in SessionData:
                    aux = SessionData["Saturation"]
                    saturation_value.set(aux)
                    if not SimulatedRun and not CameraDisabled:
                        camera.set_controls({"Saturation": aux})
                if 'AnalogueGain' in SessionData:
                    aux = SessionData["AnalogueGain"]
                    analogue_gain_value.set(aux)
                    if not SimulatedRun and not CameraDisabled:
                        camera.set_controls({"AnalogueGain": aux})
                if 'ExposureCompensation' in SessionData:
                    aux = SessionData["ExposureCompensation"]
                    exposure_compensation_value.set(aux)
                    if not SimulatedRun and not CameraDisabled:
                        camera.set_controls({"ExposureValue": aux})
                if 'SharpnessValue' in SessionData:
                    aux = int(SessionData["SharpnessValue"])  # In case it is stored as string
                    sharpness_value.set(aux)
                    if not SimulatedRun and not CameraDisabled:
                        camera.set_controls({"Sharpness": aux})

    if not AWB_enabled.get():
        camera_colour_gains = (wb_red_value.get(), wb_blue_value.get())
        camera.set_controls({"AwbEnable": False})
        camera.set_controls({"ColourGains": camera_colour_gains})

    # Update widget state whether or not config loaded (to honor app default values)
    if ExpertMode:
        arrange_widget_state(AE_enabled.get(), [exposure_spinbox])
        arrange_widget_state(not AE_enabled.get(), [auto_exposure_wait_btn,
                                                    AeConstraintMode_label, AeConstraintMode_dropdown,
                                                    AeMeteringMode_label, AeMeteringMode_dropdown,
                                                    AeExposureMode_label, AeExposureMode_dropdown])
        arrange_widget_state(not AWB_enabled.get(), [AwbMode_label, AwbMode_dropdown])
        arrange_widget_state(auto_pt_level_enabled.get(), [pt_level_spinbox])
        arrange_widget_state(auto_framesteps_enabled.get(), [steps_per_frame_spinbox])
    if ExperimentalMode:
        hdr_set_controls()
        if HdrCaptureActive:  # If HDR enabled, handle automatic control settings for widgets
            arrange_widget_state(hdr_bracket_auto.get(), [hdr_max_exp_spinbox, hdr_min_exp_spinbox])


def reinit_controller():
    if not ExpertMode:
        return

    if auto_pt_level_enabled.get():
        send_arduino_command(CMD_SET_PT_LEVEL, 0)
    else:
        send_arduino_command(CMD_SET_PT_LEVEL, pt_level_value.get())

    if auto_framesteps_enabled.get():
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0)
    else:
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, steps_per_frame_value.get())

    if 'FilmType' in SessionData:
        if SessionData["FilmType"] == "R8":
            send_arduino_command(CMD_SET_REGULAR_8)
        else:
            send_arduino_command(CMD_SET_SUPER_8)

    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, frame_fine_tune_value.get())
    send_arduino_command(CMD_SET_EXTRA_STEPS, frame_extra_steps_value.get())
    send_arduino_command(CMD_SET_SCAN_SPEED, scan_speed_value.get())


def PiCam2_change_resolution():
    target_res = resolution_dropdown_selected.get()
    camera_resolutions.set_active(target_res)
    if SimulatedRun or CameraDisabled:
        return  # Skip camera specific part

    capture_config["main"]["size"] = camera_resolutions.get_image_resolution()
    # capture_config["main"]["format"] = camera_resolutions.get_format()
    capture_config["raw"]["size"] = camera_resolutions.get_sensor_resolution()
    capture_config["raw"]["format"] = camera_resolutions.get_format()
    camera.stop()
    camera.configure(capture_config)
    camera.start()


def PiCam2_configure():
    global capture_config, preview_config

    camera.stop()
    capture_config = camera.create_still_configuration(main={"size": camera_resolutions.get_sensor_resolution()},
                                                       raw={"size": camera_resolutions.get_sensor_resolution(),
                                                            "format": camera_resolutions.get_format()},
                                                       transform=Transform(hflip=True))

    preview_config = camera.create_preview_configuration({"size": (2028, 1520)}, transform=Transform(hflip=True))
    # Camera preview window is not saved in configuration, so always off on start up (we start in capture mode)
    camera.configure(capture_config)
    # WB controls
    camera.set_controls({"AwbEnable": False})
    camera.set_controls({"ColourGains": (2.2, 2.2)})  # 0.0 to 32.0, Red 2.2, Blue 2.2 seem to be OK
    # Exposure controls
    camera.set_controls({"AeEnable": True})
    camera.set_controls(
        {"AeConstraintMode": controls.AeConstraintModeEnum.Normal})  # Normal, Highlight, Shadows, Custom
    camera.set_controls(
        {"AeMeteringMode": controls.AeMeteringModeEnum.CentreWeighted})  # CentreWeighted, Spot, Matrix, Custom
    camera.set_controls({"AeExposureMode": controls.AeExposureModeEnum.Normal})  # Normal, Long, Short, Custom
    # Other generic controls
    camera.set_controls({"AnalogueGain": 1.0})
    camera.set_controls({"Contrast": 1})  # 0.0 to 32.0
    camera.set_controls({"Brightness": 0})  # -1.0 to 1.0
    camera.set_controls({"Saturation": 1})  # Color saturation, 0.0 to 32.0
    # camera.set_controls({"NoiseReductionMode": draft.NoiseReductionModeEnum.HighQuality})   # Off, Fast, HighQuality
    camera.set_controls({"Sharpness": 1})  # It can be a floating point number from 0.0 to 16.0
    # draft.NoiseReductionModeEnum.HighQuality not defined, yet
    # However, looking at the PiCamera2 Source Code, it seems the default value for still configuration
    # is already HighQuality, so not much to worry about
    # camera.set_controls({"NoiseReductionMode": draft.NoiseReductionModeEnum.HighQuality})
    # No preview by default
    camera.options[
        'quality'] = 100  # jpeg quality: values from 0 to 100. Reply from David Plowman in PiCam2 list. Test with 60?
    camera.start(show_preview=False)


def hdr_init():
    global hdr_view_4_image

    hdr_view_4_image = Image.new("RGB", (PreviewWidth, PreviewHeight))
    hdr_reinit()


def hdr_reinit():
    global hdr_exp_list, hdr_rev_exp_list, hdr_num_exposures

    if not ExperimentalMode:
        return
    if hdr_num_exposures == 3:
        hdr_exp_list.clear()
        hdr_exp_list += [hdr_min_exp_value.get(), hdr_best_exp, hdr_max_exp_value.get()]
    elif hdr_num_exposures == 5:
        hdr_exp_list.clear()
        hdr_exp_list += [hdr_min_exp_value.get(),
                         hdr_min_exp_value.get() + int((hdr_best_exp - hdr_min_exp_value.get()) / 2), hdr_best_exp,
                         hdr_best_exp + int((hdr_max_exp_value.get() - hdr_best_exp) / 2), hdr_max_exp_value.get()]

    hdr_exp_list.sort()
    logging.debug("hdr_exp_list=%s", hdr_exp_list)
    hdr_rev_exp_list = list(reversed(hdr_exp_list))


def on_configure_scrolled_canvas(event):
    scrolled_canvas.configure(scrollregion=scrolled_canvas.bbox("all"))


def create_main_window():
    global win
    global plotter_width, plotter_height
    global PreviewWinX, PreviewWinY, app_width, app_height, original_app_height, PreviewWidth, PreviewHeight
    global FontSize
    global TopWinX, TopWinY
    global WinInitDone, as_tooltips
    global FilmHoleY_Top, FilmHoleY_Bottom, FilmHoleHeightTop, FilmHoleHeightBottom
    global screen_width, screen_height
    resolution_font = [(629, 6), (677, 7), (728, 8), (785, 9), (831, 10), (895, 11), (956, 12), (1005, 13), (1045, 14),
                       (1103, 15),
                       (1168, 16), (1220, 17), (1273, 18)]

    win = tkinter.Tk()  # creating the main window and storing the window object in 'win'
    if SimulatedRun:
        win.wm_title(string='ALT-Scann8 v' + __version__ + ' ***  SIMULATED RUN, NOT OPERATIONAL ***')
    else:
        win.title('ALT-Scann8 v' + __version__)  # setting title of the window
    # Get screen size - maxsize gives the usable screen size
    screen_width, screen_height = win.maxsize()
    logging.info(f"Screen size: {screen_width}x{screen_height}")

    # Determine optimal font size
    if FontSize == 0:
        FontSize = 5
        for resfont in resolution_font:
            if resfont[0] + 128 < screen_height:
                FontSize = resfont[1]
            else:
                break
        logging.info(f"Font size: {FontSize}")
    PreviewWidth = 700
    PreviewHeight = int(PreviewWidth / (4 / 3))
    app_width = PreviewWidth + 420
    app_height = PreviewHeight + 50
    # Set minimum plotter size, to be adjusted later based on left frame width
    plotter_width = 20
    plotter_height = 10
    # Size and position of hole markers
    FilmHoleHeightTop = int(PreviewHeight / 5.9)
    FilmHoleHeightBottom = int(PreviewHeight / 3.7)
    FilmHoleY_Top = 6
    FilmHoleY_Bottom = int(PreviewHeight / 1.25)
    if ExpertMode or ExperimentalMode:
        app_height += 325
    # Check if window fits on screen, otherwise reduce and add scroll bar
    if app_height > screen_height:
        app_height = screen_height - 128
    # Save original ap height for toggle UI button
    original_app_height = app_height
    # Prevent window resize
    win.minsize(app_width, app_height)
    win.maxsize(app_width, app_height)
    win.geometry(f'{app_width}x{app_height - 20}')  # setting the size of the window
    if 'WindowPos' in SessionData:
        win.geometry(f"+{SessionData['WindowPos'].split('+', 1)[1]}")

    # Catch closing with 'X' button
    win.protocol("WM_DELETE_WINDOW", exit_app)

    # Init ToolTips
    as_tooltips = Tooltips(FontSize)

    create_widgets()

    logging.info(f"Window size: {app_width}x{app_height + 20}")

    # Get Top window coordinates
    TopWinX = win.winfo_x()
    TopWinY = win.winfo_y()

    # Change preview coordinated for PiCamera2 to avoid confusion with overlay mode in PiCamera legacy
    PreviewWinX = 250
    PreviewWinY = 150
    WinInitDone = True


def tscann8_init():
    global camera
    global i2c
    global CurrentDir
    global ZoomSize
    global capture_display_queue, capture_display_event
    global capture_save_queue, capture_save_event
    global MergeMertens, camera_resolutions
    global active_threads
    global time_save_image, time_preview_display, time_awb, time_autoexp

    # Initialize logging
    log_path = os.path.dirname(__file__)
    if log_path == "":
        log_path = os.getcwd()
    log_file_fullpath = log_path + "/ALT-Scann8." + time.strftime("%Y%m%d") + ".log"
    logging.basicConfig(
        level=LogLevel,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file_fullpath),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logging.info("ALT-Scann8 %s (%s)", __version__, __date__)
    logging.info("Log file: %s", log_file_fullpath)
    logging.info("Config file: %s", PersistedDataFilename)

    if SimulatedRun:
        logging.info("Not running on Raspberry Pi, simulated run for UI debugging purposes only")
    else:
        logging.info("Running on Raspberry Pi")

    # Try to determine Video folder of user logged in
    homefolder = os.environ['HOME']
    if os.path.isdir(os.path.join(homefolder, 'Videos')):
        BaseDir = os.path.join(homefolder, 'Videos')
    elif os.path.isdir(os.path.join(homefolder, 'Vídeos')):
        BaseDir = os.path.join(homefolder, 'Vídeos')
    elif os.path.isdir(os.path.join(homefolder, 'Video')):
        BaseDir = os.path.join(homefolder, 'Video')
    else:
        BaseDir = homefolder
    CurrentDir = BaseDir
    logging.debug("BaseDir=%s", BaseDir)

    if not SimulatedRun:
        i2c = smbus.SMBus(1)
        # Set the I2C clock frequency to 400 kHz
        i2c.write_byte_data(16, 0x0F, 0x46)  # I2C_SCLL register
        i2c.write_byte_data(16, 0x10, 0x47)  # I2C_SCLH register

    if not SimulatedRun and not CameraDisabled:  # Init PiCamera2 here, need resolution list for drop down
        camera = Picamera2()
        camera_resolutions = CameraResolutions(camera.sensor_modes)
        logging.info(f"Camera Sensor modes: {camera.sensor_modes}")
        PiCam2_configure()
        ZoomSize = camera.capture_metadata()['ScalerCrop'][2:]
    if SimulatedRun:
        # Initializes resolution list from a hardcoded sensor_modes
        camera_resolutions = CameraResolutions(simulated_sensor_modes)

        # Initialize rolling average objects
    time_save_image = RollingAverage(50)
    time_preview_display = RollingAverage(50)
    time_awb = RollingAverage(50)
    time_autoexp = RollingAverage(50)

    create_main_window()

    # Init HDR variables
    hdr_init()
    # Create MergeMertens Object for HDR
    MergeMertens = cv2.createMergeMertens()

    reset_controller()

    get_controller_version()

    send_arduino_command(CMD_REPORT_PLOTTER_INFO, PlotterMode)

    win.update_idletasks()

    if not SimulatedRun and not CameraDisabled:
        # JRE 20/09/2022: Attempt to speed up overall process in PiCamera2 by having captured images
        # displayed in the preview area by a dedicated thread, so that time consumed in this task
        # does not impact the scan process speed
        capture_display_queue = queue.Queue(maxsize=MaxQueueSize)
        capture_display_event = threading.Event()
        capture_save_queue = queue.Queue(maxsize=MaxQueueSize)
        capture_save_event = threading.Event()
        display_thread = threading.Thread(target=capture_display_thread, args=(capture_display_queue,
                                                                               capture_display_event, 0))
        save_thread_1 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event, 1))
        save_thread_2 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event, 2))
        save_thread_3 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event, 3))
        active_threads += 4
        display_thread.start()
        save_thread_1.start()
        save_thread_2.start()
        save_thread_3.start()
        logging.debug("Threads initialized")

    logging.debug("ALT-Scann 8 initialized")


# **************************************************
# ********** Widget entries validation *************
# **************************************************
def value_normalize(var, min_value, max_value, default):
    try:
        value = var.get()
    except tk.TclError as e:
        var.set(default)
        return min_value
    if value > max_value or value < min_value:
        value = default
    var.set(value)
    return value


def value_validation(new_value, widget, min, max, default, is_double=False):
    try:
        if new_value == '':
            new_value = default
        if is_double:
            aux = float(new_value)
        else:
            aux = int(new_value)
        if min <= aux <= max:
            widget.config(fg='black')
            return True
        elif aux < min or aux > max:
            widget.config(fg='red')
            return True
        else:
            return False
    except (ValueError, TypeError):
        return False


def set_auto_exposure():
    aux = 0 if AE_enabled.get() else int(exposure_value.get() * 1000)
    auto_exposure_btn.config(text="Auto Exp:" if AE_enabled.get() else "Exposure:")
    arrange_widget_state(AE_enabled.get(), [exposure_spinbox])
    arrange_widget_state(not AE_enabled.get(), [auto_exposure_wait_btn,
                                                AeConstraintMode_label, AeConstraintMode_dropdown,
                                                AeMeteringMode_label, AeMeteringMode_dropdown,
                                                AeExposureMode_label, AeExposureMode_dropdown])

    if not SimulatedRun and not CameraDisabled:
        # Do not retrieve current gain values from Camera (capture_metadata) to prevent conflicts
        # Since we update values in the UI regularly, use those.
        camera.set_controls({"AeEnable": True if aux == 0 else False})
        camera.set_controls({"ExposureTime": aux})

    SessionData["CurrentExposure"] = aux


def auto_exposure_change_pause_selection():
    SessionData["ExposureAdaptPause"] = auto_exposure_change_pause.get()


def exposure_selection():
    if AE_enabled.get():  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return
    aux = value_normalize(exposure_value, camera_resolutions.get_min_exp() / 1000,
                          camera_resolutions.get_max_exp() / 1000,
                          100)
    aux = aux * 1000
    if aux <= 0:
        aux = camera_resolutions.get_min_exp()  # Minimum exposure is 1µs, zero means automatic
    SessionData["CurrentExposure"] = aux

    if not SimulatedRun and not CameraDisabled:
        camera.controls.ExposureTime = int(aux)  # maybe will not work, check pag 26 of picamera2 specs


def exposure_validation(new_value):
    # Use zero instead if minimum exposure from PiCamera2 to prevent flagging in red when selection auto exposure
    return value_validation(new_value, exposure_spinbox, 0, camera_resolutions.get_max_exp() / 1000,
                            100, True)


def wb_red_selection():
    global manual_wb_red_value
    if AWB_enabled.get():  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return

    aux = value_normalize(wb_red_value, 0, 32, 2.2)
    manual_wb_red_value = aux
    SessionData["GainRed"] = aux

    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ColourGains": (aux, wb_blue_value.get())})


def wb_red_validation(new_value):
    return value_validation(new_value, wb_red_spinbox, 0, 32, 2.2, True)


def wb_blue_selection():
    global manual_wb_blue_value
    if AWB_enabled.get():  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return

    aux = value_normalize(wb_blue_value, 0, 32, 2.2)
    manual_wb_blue_value = aux
    SessionData["GainBlue"] = aux

    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ColourGains": (wb_red_value.get(), aux)})


def wb_blue_validation(new_value):
    return value_validation(new_value, wb_blue_spinbox, 0, 32, 2.2, True)


def match_wait_margin_selection():
    aux = value_normalize(match_wait_margin_value, 5, 100, 50)
    SessionData["MatchWaitMargin"] = aux


def match_wait_margin_validation(new_value):
    return value_validation(new_value, match_wait_margin_spinbox, 5, 100, 50)


def set_AeConstraintMode(selected):
    SessionData["AeConstraintMode"] = selected
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AeConstraintMode": AeConstraintMode_dict[selected]})


def set_AeMeteringMode(selected):
    SessionData["AeMeteringMode"] = selected
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AeMeteringMode": AeMeteringMode_dict[selected]})


def set_AeExposureMode(selected):
    SessionData["AeExposureMode"] = selected
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AeExposureMode": AeExposureMode_dict[selected]})


def set_AwbMode(selected):
    SessionData["AwbMode"] = selected
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AwbMode": AwbMode_dict[selected]})


def steps_per_frame_auto():
    arrange_widget_state(auto_framesteps_enabled.get(), [steps_per_frame_spinbox])
    steps_per_frame_btn.config(text="Steps/Frame AUTO:" if auto_framesteps_enabled.get() else "Steps/Frame:")
    SessionData["FrameStepsAuto"] = auto_framesteps_enabled.get()
    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if auto_framesteps_enabled.get() else steps_per_frame_value.get())


def steps_per_frame_selection():
    if auto_framesteps_enabled.get():
        return
    MinFrameSteps = value_normalize(steps_per_frame_value, 100, 600, 250)
    SessionData["MinFrameSteps"] = MinFrameSteps
    SessionData["MinFrameSteps" + SessionData["FilmType"]] = MinFrameSteps
    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, MinFrameSteps)


def steps_per_frame_validation(new_value):
    return value_validation(new_value, steps_per_frame_spinbox, 100, 600, 250)


def set_auto_pt_level():
    arrange_widget_state(auto_pt_level_enabled.get(), [pt_level_spinbox])
    pt_level_btn.config(text="PT Level AUTO:" if auto_pt_level_enabled.get() else "PT Level:")
    SessionData["PTLevelAuto"] = auto_pt_level_enabled.get()
    send_arduino_command(CMD_SET_PT_LEVEL, 0 if auto_pt_level_enabled.get() else pt_level_value.get())


def pt_level_selection():
    if auto_pt_level_enabled.get():
        return
    PTLevel = value_normalize(pt_level_value, 20, 900, 500)
    SessionData["PTLevel"] = PTLevel
    SessionData["PTLevel" + SessionData["FilmType"]] = PTLevel
    send_arduino_command(CMD_SET_PT_LEVEL, PTLevel)


def pt_level_validation(new_value):
    return value_validation(new_value, pt_level_spinbox, 20, 900, 500)


def frame_fine_tune_selection():
    aux = value_normalize(frame_fine_tune_value, 5, 95, 25)
    SessionData["FrameFineTune"] = aux
    SessionData["FrameFineTune" + SessionData["FilmType"]] = aux
    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, aux)


def fine_tune_validation(new_value):
    return value_validation(new_value, frame_fine_tune_spinbox, 5, 95, 25)


def extra_steps_validation(new_value):
    return value_validation(new_value, frame_extra_steps_spinbox, -30, 30, 0)


def scan_speed_selection():
    aux = value_normalize(scan_speed_value, 1, 10, 5)
    SessionData["ScanSpeed"] = aux
    send_arduino_command(CMD_SET_SCAN_SPEED, aux)


def scan_speed_validation(new_value):
    return value_validation(new_value, scan_speed_spinbox, 1, 10, 5)


def preview_module_selection():
    aux = value_normalize(preview_module_value, 1, 50, 1)
    SessionData["PreviewModule"] = aux


def preview_module_validation(new_value):
    return value_validation(new_value, preview_module_spinbox, 1, 50, 1)


def stabilization_delay_selection():
    aux = value_normalize(stabilization_delay_value, 0, 1000, 150)
    aux = aux / 1000
    SessionData["CaptureStabilizationDelay"] = aux


def stabilization_delay_validation(new_value):
    return value_validation(new_value, stabilization_delay_spinbox, 0, 1000, 150)


def hdr_min_exp_selection():
    global force_adjust_hdr_bracket, recalculate_hdr_exp_list

    min_exp = value_normalize(hdr_min_exp_value, hdr_lower_exp, 999, 100)
    bracket = hdr_bracket_width_value.get()
    max_exp = min_exp + bracket  # New max based on new min
    if max_exp > 1000:
        bracket -= max_exp - 1000  # Reduce bracket in max over the top
        max_exp = 1000
        force_adjust_hdr_bracket = True
    hdr_min_exp_value.set(min_exp)
    hdr_max_exp_value.set(max_exp)
    hdr_bracket_width_value.set(bracket)
    recalculate_hdr_exp_list = True
    SessionData["HdrMinExp"] = min_exp
    SessionData["HdrMaxExp"] = max_exp
    SessionData["HdrBracketWidth"] = bracket


def hdr_min_exp_validation(new_value):
    return value_validation(new_value, hdr_min_exp_spinbox, hdr_lower_exp, 999, 100)


def hdr_max_exp_selection():
    global recalculate_hdr_exp_list
    global force_adjust_hdr_bracket

    max_exp = value_normalize(hdr_max_exp_value, 2, 1000, 200)
    bracket = hdr_bracket_width_value.get()
    min_exp = max_exp - bracket
    if min_exp < hdr_lower_exp:
        min_exp = hdr_lower_exp
        bracket = max_exp - min_exp  # Reduce bracket in min below absolute min
        force_adjust_hdr_bracket = True
    hdr_min_exp_value.set(min_exp)
    hdr_max_exp_value.set(max_exp)
    hdr_bracket_width_value.set(bracket)
    recalculate_hdr_exp_list = True
    SessionData["HdrMinExp"] = min_exp
    SessionData["HdrMaxExp"] = max_exp
    SessionData["HdrBracketWidth"] = bracket


def hdr_max_exp_validation(new_value):
    return value_validation(new_value, hdr_max_exp_spinbox, 2, 1000, 200)


def hdr_bracket_width_selection():
    global force_adjust_hdr_bracket

    aux_bracket = value_normalize(hdr_bracket_width_value, hdr_min_bracket_width, hdr_max_bracket_width, 200)

    middle_exp = int((hdr_min_exp_value.get() + (hdr_max_exp_value.get() - hdr_min_exp_value.get())) / 2)
    hdr_min_exp_value.set(int(middle_exp - (aux_bracket / 2)))
    if hdr_min_exp_value.get() < hdr_lower_exp:
        hdr_min_exp_value.set(hdr_lower_exp)
        hdr_max_exp_value.set(hdr_min_exp_value.get() + aux_bracket)
    else:
        hdr_max_exp_value.set(int(middle_exp + (aux_bracket / 2)))
    SessionData["HdrMinExp"] = hdr_min_exp_value.get()
    SessionData["HdrMaxExp"] = hdr_max_exp_value.get()
    SessionData["HdrBracketWidth"] = hdr_bracket_width_value.get()
    force_adjust_hdr_bracket = True


def hdr_bracket_width_validation(new_value):
    return value_validation(new_value, hdr_bracket_width_spinbox, hdr_min_bracket_width, hdr_max_bracket_width,
                            100)


def hdr_bracket_shift_selection():
    value_normalize(hdr_bracket_shift_value, -100, 100, 0)


def hdr_bracket_shift_validation(new_value):
    return value_validation(new_value, hdr_bracket_shift_spinbox, -100, 100, 0)


def exposure_compensation_selection():
    aux = value_normalize(exposure_compensation_value, -8, 8, 0)
    SessionData["ExposureCompensation"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ExposureValue": aux})


def exposure_compensation_validation(new_value):
    return value_validation(new_value, exposure_compensation_spinbox, -8, 8, 0)


def brightness_selection():
    aux = value_normalize(brightness_value, -1, 1, 0)
    SessionData["Brightness"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"Brightness": aux})


def brightness_validation(new_value):
    return value_validation(new_value, brightness_spinbox, -1, 1, 0)


def contrast_selection():
    aux = value_normalize(contrast_value, 0, 32, 1)
    SessionData["Contrast"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"Contrast": aux})


def contrast_validation(new_value):
    return value_validation(new_value, contrast_spinbox, 0, 32, 1)


def saturation_selection():
    aux = value_normalize(saturation_value, 0, 32, 1)
    SessionData["Saturation"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"Saturation": aux})


def saturation_validation(new_value):
    return value_validation(new_value, saturation_spinbox, 0, 32, 1)


def analogue_gain_selection():
    aux = value_normalize(analogue_gain_value, 0, 32, 0)
    SessionData["AnalogueGain"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AnalogueGain": aux})


def analogue_gain_validation(new_value):
    return value_validation(new_value, analogue_gain_spinbox, 0, 32, 0)


def sharpness_selection():
    aux = value_normalize(sharpness_value, 0, 16, 1)
    SessionData["SharpnessValue"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"Sharpness": aux})


def sharpness_validation(new_value):
    return value_validation(new_value, sharpness_spinbox, 0, 16, 1)


def rwnd_speed_control_selection():
    value_normalize(rwnd_speed_control_value, 40, 800, 800)


def rewind_speed_validation(new_value):
    return value_validation(new_value, rwnd_speed_control_spinbox, 40, 800, 800)


def update_target_dir_wraplength(event):
    folder_frame_target_dir.config(wraplength=event.width - 20)  # Adjust the padding as needed


# ***************
# Widget creation
# ***************
def create_widgets():
    global AdvanceMovie_btn
    global SingleStep_btn
    global Snapshot_btn
    global negative_image_checkbox, negative_image
    global Rewind_btn
    global FastForward_btn
    global Free_btn
    global RPi_temp_value_label
    global Exit_btn
    global Start_btn
    global folder_frame_target_dir
    global exposure_frame
    global film_type_S8_rb, film_type_R8_rb, film_type
    global save_bg, save_fg
    global PreviewStatus
    global auto_exposure_change_pause
    global auto_exposure_wait_btn
    global decrease_exp_btn, increase_exp_btn
    global temp_in_fahrenheit
    global auto_white_balance_change_pause
    global auto_wb_wait_btn
    global film_hole_frame_top, film_hole_frame_bottom
    global FilmHoleHeightTop, FilmHoleHeightBottom, FilmHoleY_Top, FilmHoleY_Bottom
    global temp_in_fahrenheit_checkbox
    global real_time_display_checkbox, real_time_display
    global real_time_zoom_checkbox, real_time_zoom
    global auto_stop_enabled_checkbox, auto_stop_enabled
    global focus_lf_btn, focus_up_btn, focus_dn_btn, focus_rt_btn, focus_plus_btn, focus_minus_btn
    global draw_capture_canvas
    global hdr_btn
    global steps_per_frame_value, frame_fine_tune_value
    global pt_level_spinbox
    global steps_per_frame_spinbox, frame_fine_tune_spinbox, pt_level_spinbox, pt_level_value
    global frame_extra_steps_spinbox, frame_extra_steps_value
    global scan_speed_spinbox, scan_speed_value
    global exposure_value
    global wb_red_spinbox, wb_blue_spinbox, wb_red_value, wb_blue_value
    global match_wait_margin_spinbox, match_wait_margin_value
    global stabilization_delay_spinbox, stabilization_delay_value
    global sharpness_spinbox, sharpness_value
    global rwnd_speed_control_spinbox, rwnd_speed_control_value
    global Manual_scan_activated, ManualScanEnabled, manual_scan_take_snap_btn
    global manual_scan_advance_fraction_5_btn, manual_scan_advance_fraction_20_btn
    global plotter_canvas
    global hdr_capture_active_checkbox, hdr_capture_active, hdr_viewx4_active
    global hdr_viewx4_active_checkbox, hdr_min_exp_label, hdr_min_exp_spinbox, hdr_max_exp_label, hdr_max_exp_spinbox
    global hdr_max_exp_value, hdr_min_exp_value
    global steps_per_frame_btn, auto_framesteps_enabled, pt_level_btn, auto_pt_level_enabled
    global auto_exposure_btn, auto_wb_red_btn, auto_wb_blue_btn, exposure_spinbox, wb_red_spinbox, wb_blue_spinbox
    global hdr_bracket_width_spinbox, hdr_bracket_shift_spinbox, hdr_bracket_width_label, hdr_bracket_shift_label
    global hdr_bracket_width_value, hdr_bracket_shift_value
    global hdr_bracket_auto, hdr_bracket_width_auto_checkbox
    global hdr_merge_in_place, hdr_bracket_width_auto_checkbox, hdr_merge_in_place_checkbox
    global frames_to_go_str, FramesToGo, time_to_go_str
    global RetreatMovie_btn, Manual_scan_checkbox
    global file_type_dropdown, file_type_dropdown_selected
    global resolution_dropdown, resolution_dropdown_selected
    global Scanned_Images_number_str, Scanned_Images_time_str, Scanned_Images_Fpm_str
    global resolution_label, resolution_dropdown, file_type_label, file_type_dropdown
    global existing_folder_btn, new_folder_btn
    global autostop_no_film_rb, autostop_counter_zero_rb, autostop_type
    global full_ui_checkbox, toggle_ui_small
    global AE_enabled, AWB_enabled
    global extended_frame, expert_frame, experimental_frame
    global time_save_image_value, time_preview_display_value, time_awb_value, time_autoexp_value
    global AeConstraintMode_dropdown_selected, AeMeteringMode_dropdown_selected, AeExposureMode_dropdown_selected
    global AwbMode_dropdown_selected
    global AeConstraintMode_dropdown, AeMeteringMode_dropdown, AeExposureMode_dropdown, AwbMode_dropdown
    global AeConstraintMode_label, AeMeteringMode_label, AeExposureMode_label, AwbMode_label
    global brightness_value, contrast_value, saturation_value, analogue_gain_value, exposure_compensation_value
    global preview_module_value
    global brightness_spinbox, contrast_spinbox, saturation_spinbox, analogue_gain_spinbox
    global exposure_compensation_spinbox, preview_module_spinbox
    global scrolled_canvas
    global PreviewWidth, PreviewHeight
    global plotter_width, plotter_height
    global app_width, app_height

    # Global value for separations between widgets
    y_pad = 2
    x_pad = 2

    # Check if vertical scrollbar required
    if add_vertical_scrollbar:
        # Create a canvas widget
        scrolled_canvas = tk.Canvas(win)

        # Add a horizontal scrollbar to the canvas
        scrolled_canvas_scrollbar_h = tk.Scrollbar(win, orient=tk.HORIZONTAL, command=scrolled_canvas.xview)
        scrolled_canvas_scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)

        scrolled_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add a vertical scrollbar to the canvas
        scrolled_canvas_scrollbar_v = tk.Scrollbar(win, command=scrolled_canvas.yview)
        scrolled_canvas_scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure the canvas to use the scrollbar
        scrolled_canvas.configure(xscrollcommand=scrolled_canvas_scrollbar_h.set,
                                  yscrollcommand=scrolled_canvas_scrollbar_v.set)

        # Create a frame inside the canvas to hold the content
        scrolled_frame = tk.Frame(scrolled_canvas)
        scrolled_canvas.create_window((0, 0), window=scrolled_frame, anchor="nw")

        # Bind the frame to the canvas so it resizes properly
        scrolled_frame.bind("<Configure>", on_configure_scrolled_canvas)

        main_container = scrolled_frame
    else:
        scrolled_canvas = None
        main_container = win

    # Create a frame to contain the top area (preview + Right buttons) ***************
    top_area_frame = Frame(main_container)
    top_area_frame.pack(side=TOP, pady=(8, 0), anchor=NW, fill='both')

    # Create a frame to contain the top right area (buttons) ***************
    top_left_area_frame = Frame(top_area_frame)
    top_left_area_frame.pack(side=LEFT, anchor=N, padx=(10, 0))
    # Create a LabelFrame to act as a border of preview canvas
    draw_capture_frame = tk.LabelFrame(top_area_frame, bd=2, relief=tk.GROOVE)
    draw_capture_frame.pack(side=LEFT, anchor=N, padx=(10, 0), pady=(2, 0))  # Pady+=2 to compensate
    # Create the canvas
    draw_capture_canvas = Canvas(draw_capture_frame, bg='dark grey', width=PreviewWidth, height=PreviewHeight)
    draw_capture_canvas.pack(padx=(20, 5), pady=5)
    # Create a frame to contain the top right area (buttons) ***************
    top_right_area_frame = Frame(top_area_frame)
    top_right_area_frame.pack(side=LEFT, anchor=N, padx=(10, 0))

    # ***************************************
    # Display markers for film hole reference
    # Size & postition of markers relative to preview height
    film_hole_frame_top = Frame(draw_capture_frame, width=1, height=1, bg='black')
    film_hole_frame_top.pack(side=TOP, padx=1, pady=1)
    film_hole_frame_top.place(x=0, y=FilmHoleY_Top, height=FilmHoleHeightTop)
    film_hole_label_1 = Label(film_hole_frame_top, justify=LEFT, font=("Arial", FontSize), width=2, height=11,
                              bg='white', fg='white')
    film_hole_label_1.pack(side=TOP)

    film_hole_frame_bottom = Frame(draw_capture_frame, width=1, height=1, bg='black')
    film_hole_frame_bottom.pack(side=TOP, padx=1, pady=1)
    film_hole_frame_bottom.place(x=0, y=FilmHoleY_Bottom, height=FilmHoleHeightBottom)
    film_hole_label_2 = Label(film_hole_frame_bottom, justify=LEFT, font=("Arial", FontSize), width=2, height=11,
                              bg='white', fg='white')
    film_hole_label_2.pack(side=TOP)

    # Advance movie button (slow forward through filmgate)
    bottom_area_column = 0
    bottom_area_row = 0
    AdvanceMovie_btn = Button(top_left_area_frame, text="Movie Forward", command=advance_movie,
                              activebackground='#f0f0f0', relief=RAISED, font=("Arial", FontSize))
    AdvanceMovie_btn.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad, pady=y_pad,
                          sticky='NSEW')
    as_tooltips.add(AdvanceMovie_btn, "Advance film (can be used with real-time view enabled).")
    bottom_area_row += 1
    # Once first button created, get default colors, to revert when we change them
    save_bg = AdvanceMovie_btn['bg']
    save_fg = AdvanceMovie_btn['fg']

    # Frame for single step/snapshot
    sstep_area_frame = Frame(top_left_area_frame)
    sstep_area_frame.grid_forget()
    # Advance one single frame
    SingleStep_btn = Button(sstep_area_frame, text="Single Step", command=single_step_movie,
                            activebackground='#f0f0f0', font=("Arial", FontSize))
    SingleStep_btn.grid_forget()
    Snapshot_btn = Button(sstep_area_frame, text="Snapshot", command=capture_single_step,
                          activebackground='#f0f0f0', font=("Arial", FontSize))
    Snapshot_btn.grid_forget()

    # Rewind movie (via upper path, outside of film gate)
    Rewind_btn = Button(top_left_area_frame, text="<<", font=("Arial", FontSize + 3), height=2, command=rewind_movie,
                        activebackground='#f0f0f0', relief=RAISED)
    Rewind_btn.grid(row=bottom_area_row, column=bottom_area_column, padx=x_pad, pady=y_pad, sticky='NSEW')
    as_tooltips.add(Rewind_btn, "Rewind film. Make sure film is routed via upper rolls.")
    # Fast Forward movie (via upper path, outside of film gate)
    FastForward_btn = Button(top_left_area_frame, text=">>", font=("Arial", FontSize + 3), height=2,
                             command=fast_forward_movie, activebackground='#f0f0f0', relief=RAISED)
    FastForward_btn.grid(row=bottom_area_row, column=bottom_area_column + 1, padx=x_pad, pady=y_pad, sticky='NSEW')
    as_tooltips.add(FastForward_btn, "Fast-forward film. Make sure film is routed via upper rolls.")
    bottom_area_row += 1

    # Switch Positive/negative modes
    negative_image = tk.BooleanVar(value=False)
    negative_image_checkbox = tk.Checkbutton(top_left_area_frame, text='Negative film',
                                             variable=negative_image, onvalue=True, offvalue=False,
                                             font=("Arial", FontSize), command=set_negative_image,
                                             indicatoron=False, selectcolor="pale green")
    negative_image_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad, pady=y_pad,
                                 sticky='NSEW')
    as_tooltips.add(negative_image_checkbox, "Enable negative film capture (untested with real negative film)")
    bottom_area_row += 1

    # Real time view to allow focus
    real_time_display = tk.BooleanVar(value=False)
    real_time_display_checkbox = tk.Checkbutton(top_left_area_frame, text='Focus view', height=1,
                                                variable=real_time_display, onvalue=True, offvalue=False,
                                                font=("Arial", FontSize), command=set_real_time_display,
                                                indicatoron=False, selectcolor="pale green")
    real_time_display_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad,
                                    pady=y_pad, sticky='NSEW')
    as_tooltips.add(real_time_display_checkbox, "Enable real-time film preview. Cannot be used while scanning, "
                                                "useful mainly to focus the film.")
    bottom_area_row += 1

    # Activate focus zoom, to facilitate focusing the camera
    real_time_zoom = tk.BooleanVar(value=False)
    real_time_zoom_checkbox = tk.Checkbutton(top_left_area_frame, text='Zoom view', height=1,
                                             variable=real_time_zoom, onvalue=True, offvalue=False,
                                             font=("Arial", FontSize), command=set_focus_zoom, indicatoron=False,
                                             selectcolor="pale green", state=DISABLED)
    real_time_zoom_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad, pady=y_pad,
                                 sticky='NSEW')
    as_tooltips.add(real_time_zoom_checkbox, "Zoom in on the real-time film preview. Useful to focus the film")
    bottom_area_row += 1

    # Focus zoom control (in out, up, down, left, right)
    Focus_frame = LabelFrame(top_left_area_frame, text='Zoom control', height=3, font=("Arial", FontSize - 2))
    Focus_frame.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad, pady=y_pad,
                     sticky='NSEW')
    bottom_area_row += 1

    Focus_btn_grid_frame = Frame(Focus_frame)
    Focus_btn_grid_frame.pack(padx=x_pad, pady=y_pad)

    # focus zoom displacement buttons, to further facilitate focusing the camera
    focus_plus_btn = Button(Focus_btn_grid_frame, text="+", height=1, command=set_focus_plus,
                            activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize - 2))
    focus_plus_btn.grid(row=0, column=2, sticky='NSEW')
    as_tooltips.add(focus_plus_btn, "Increase zoom level.")
    focus_minus_btn = Button(Focus_btn_grid_frame, text="-", height=1, command=set_focus_minus,
                             activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize - 2))
    focus_minus_btn.grid(row=0, column=0, sticky='NSEW')
    as_tooltips.add(focus_minus_btn, "Decrease zoom level.")
    focus_lf_btn = Button(Focus_btn_grid_frame, text="←", height=1, command=set_focus_left,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize - 2))
    focus_lf_btn.grid(row=1, column=0, sticky='NSEW')
    as_tooltips.add(focus_lf_btn, "Move zoom view to the left.")
    focus_up_btn = Button(Focus_btn_grid_frame, text="↑", height=1, command=set_focus_up,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize - 2))
    focus_up_btn.grid(row=0, column=1, sticky='NSEW')
    as_tooltips.add(focus_up_btn, "Move zoom view up.")
    focus_dn_btn = Button(Focus_btn_grid_frame, text="↓", height=1, command=set_focus_down,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize - 2))
    focus_dn_btn.grid(row=1, column=1, sticky='NSEW')
    as_tooltips.add(focus_dn_btn, "Move zoom view down.")
    focus_rt_btn = Button(Focus_btn_grid_frame, text="→", height=1, command=set_focus_right,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize - 2))
    focus_rt_btn.grid(row=1, column=2, sticky='NSEW')
    as_tooltips.add(focus_rt_btn, "Move zoom view to the right.")
    bottom_area_row += 1

    # Frame for automatic stop & methods
    autostop_frame = Frame(top_left_area_frame)
    autostop_frame.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad, pady=y_pad,
                        sticky='WE')

    # Activate focus zoom, to facilitate focusing the camera
    auto_stop_enabled = tk.BooleanVar(value=False)
    auto_stop_enabled_checkbox = tk.Checkbutton(autostop_frame, text='Auto-stop if', height=1,
                                                variable=auto_stop_enabled, onvalue=True, offvalue=False,
                                                font=("Arial", FontSize), command=set_auto_stop_enabled)
    auto_stop_enabled_checkbox.pack(side=TOP, anchor=W)
    as_tooltips.add(auto_stop_enabled_checkbox, "Stop scanning when end of film detected")

    # Radio buttons to select auto-stop method
    autostop_type = tk.StringVar()
    autostop_type.set('No_film')
    autostop_no_film_rb = tk.Radiobutton(autostop_frame, text="No film", variable=autostop_type,
                                         value='No_film', font=("Arial", FontSize), command=set_auto_stop_enabled)
    autostop_no_film_rb.pack(side=TOP, anchor=W, padx=(10, 0))
    as_tooltips.add(autostop_no_film_rb, "Stop when film is not detected by PT")
    autostop_counter_zero_rb = tk.Radiobutton(autostop_frame, text="Count zero", variable=autostop_type,
                                              value='counter_to_zero', font=("Arial", FontSize),
                                              command=set_auto_stop_enabled)
    autostop_counter_zero_rb.pack(side=TOP, anchor=W, padx=(10, 0))
    as_tooltips.add(autostop_counter_zero_rb, "Stop scan when frames-to-go counter reaches zero")
    autostop_no_film_rb.config(state=DISABLED)
    autostop_counter_zero_rb.config(state=DISABLED)

    bottom_area_row += 1

    # Toggle UI size & stats only in expert mode
    if ExpertMode:
        toggle_ui_small = tk.BooleanVar(value=False)
        full_ui_checkbox = tk.Checkbutton(top_left_area_frame, text='Toggle UI', height=1,
                                          variable=toggle_ui_small, onvalue=True, offvalue=False,
                                          font=("Arial", FontSize), command=toggle_ui_size, indicatoron=False,
                                          selectcolor="sea green")

        full_ui_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad, pady=y_pad,
                              sticky='NSEW')
        as_tooltips.add(full_ui_checkbox, "Toggle between full/restricted user interface")
        bottom_area_row += 1

        # Statictics sub-frame
        statistics_frame = LabelFrame(top_left_area_frame, text='Avrg time (ms)', font=("Arial", FontSize - 1))
        statistics_frame.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad, pady=y_pad,
                              sticky='NSEW')
        # Average Time to save image
        time_save_image_label = tk.Label(statistics_frame, text='Save:', font=("Arial", FontSize - 1))
        time_save_image_label.grid(row=0, column=0, sticky=E)
        as_tooltips.add(time_save_image_label, "Average time spent in saving each frame (in milliseconds)")
        time_save_image_value = tk.IntVar(value=0)
        time_save_image_value_label = tk.Label(statistics_frame, textvariable=time_save_image_value,
                                               font=("Arial", FontSize - 1))
        time_save_image_value_label.grid(row=0, column=1, sticky=W)
        as_tooltips.add(time_save_image_value_label, "Average time spent in saving each frame (in milliseconds)")
        time_save_image_label_ms = tk.Label(statistics_frame, text='ms', font=("Arial", FontSize - 1))
        time_save_image_label_ms.grid(row=0, column=2, sticky=E)
        # Average Time to display preview
        time_preview_display_label = tk.Label(statistics_frame, text='Prvw:', font=("Arial", FontSize - 1))
        time_preview_display_label.grid(row=1, column=0, sticky=E)
        as_tooltips.add(time_preview_display_label, "Average time spent in displaying a preview of each frame (in "
                                                    "milliseconds)")
        time_preview_display_value = tk.IntVar(value=0)
        time_preview_display_value_label = tk.Label(statistics_frame, textvariable=time_preview_display_value,
                                                    font=("Arial", FontSize - 1))
        time_preview_display_value_label.grid(row=1, column=1, sticky=W)
        as_tooltips.add(time_preview_display_value_label, "Average time spent in displaying a preview of each frame ("
                                                          "in milliseconds)")
        time_preview_display_label_ms = tk.Label(statistics_frame, text='ms', font=("Arial", FontSize - 1))
        time_preview_display_label_ms.grid(row=1, column=2, sticky=E)
        # Average Time spent waiting for AWB to adjust
        time_awb_label = tk.Label(statistics_frame, text='AWB:', font=("Arial", FontSize - 1))
        time_awb_label.grid(row=2, column=0, sticky=E)
        as_tooltips.add(time_awb_label, "Average time spent waiting for white balance to match automatic value (in "
                                        "milliseconds)")
        time_awb_value = tk.IntVar(value=0)
        time_awb_value_label = tk.Label(statistics_frame, textvariable=time_awb_value, font=("Arial", FontSize - 1))
        time_awb_value_label.grid(row=2, column=1, sticky=W)
        as_tooltips.add(time_awb_value_label, "Average time spent waiting for white balance to match automatic value "
                                              "(in milliseconds)")
        time_awb_label_ms = tk.Label(statistics_frame, text='ms', font=("Arial", FontSize - 1))
        time_awb_label_ms.grid(row=2, column=2, sticky=E)
        # Average Time spent waiting for AE to adjust
        time_autoexp_label = tk.Label(statistics_frame, text='AE:', font=("Arial", FontSize - 1))
        time_autoexp_label.grid(row=3, column=0, sticky=E)
        as_tooltips.add(time_autoexp_label, "Average time spent waiting for exposure to match automatic value (in "
                                            "milliseconds)")
        time_autoexp_value = tk.IntVar(value=0)
        time_autoexp_value_label = tk.Label(statistics_frame, textvariable=time_autoexp_value,
                                            font=("Arial", FontSize - 1))
        time_autoexp_value_label.grid(row=3, column=1, sticky=W)
        as_tooltips.add(time_autoexp_value_label, "Average time spent waiting for exposure to match automatic value ("
                                                  "in milliseconds)")
        time_autoexp_label_ms = tk.Label(statistics_frame, text='ms', font=("Arial", FontSize - 1))
        time_autoexp_label_ms.grid(row=3, column=2, sticky=E)
        bottom_area_row += 1

    # Create vertical button column at right *************************************
    # Application Exit button
    top_right_area_row = 0
    Exit_btn = Button(top_right_area_frame, text="Exit", height=4, command=exit_app, activebackground='red',
                      activeforeground='white', font=("Arial", FontSize))
    Exit_btn.grid(row=top_right_area_row, column=0, padx=x_pad, pady=y_pad, sticky='EW')
    as_tooltips.add(Exit_btn, "Exit ALT-Scann8.")

    # Start scan button
    if SimulatedRun:
        Start_btn = Button(top_right_area_frame, text="START Scan", height=4, command=start_scan_simulated,
                           activebackground='#f0f0f0', font=("Arial", FontSize))
    else:
        Start_btn = Button(top_right_area_frame, text="START Scan", height=4, command=start_scan,
                           activebackground='#f0f0f0', font=("Arial", FontSize))
    Start_btn.grid(row=top_right_area_row, column=1, padx=x_pad, pady=y_pad, sticky='EW')
    as_tooltips.add(Start_btn, "Start scanning process.")
    top_right_area_row += 1

    # Create frame to select target folder
    folder_frame = LabelFrame(top_right_area_frame, text='Target Folder', height=8, font=("Arial", FontSize - 2))
    folder_frame.grid(row=top_right_area_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky='EW')
    # Bind the frame's resize event to the function that updates the wraplength
    folder_frame.bind("<Configure>", update_target_dir_wraplength)

    folder_frame_target_dir = Label(folder_frame, text=CurrentDir, wraplength=150, height=3,
                                    font=("Arial", FontSize - 3))
    folder_frame_target_dir.pack(side=TOP)

    folder_frame_buttons = Frame(folder_frame, bd=2)
    folder_frame_buttons.pack()
    new_folder_btn = Button(folder_frame_buttons, text='New', command=set_new_folder,
                            activebackground='#f0f0f0', font=("Arial", FontSize - 2))
    new_folder_btn.pack(side=LEFT)
    as_tooltips.add(new_folder_btn, "Create new folder to store frames generated during the scan.")
    existing_folder_btn = Button(folder_frame_buttons, text='Existing', command=set_existing_folder,
                                 activebackground='#f0f0f0', font=("Arial", FontSize - 2))
    existing_folder_btn.pack(side=LEFT)
    as_tooltips.add(existing_folder_btn, "Select existing folder to store frames generated during the scan.")
    top_right_area_row += 1

    # Create frame to select target file specs
    file_type_frame = LabelFrame(top_right_area_frame, text='Capture resolution & file type',
                                 font=("Arial", FontSize - 2))
    file_type_frame.grid(row=top_right_area_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky='EW')

    # Capture resolution Dropdown
    # Drop down to select capture resolution
    # Dropdown menu options
    resolution_list = camera_resolutions.get_list()
    resolution_dropdown_selected = tk.StringVar()
    resolution_dropdown_selected.set(resolution_list[1])  # Set the initial value
    resolution_label = Label(file_type_frame, text='Resolution:', font=("Arial", FontSize))
    # resolution_label.pack(side=LEFT)
    resolution_label.pack_forget()
    resolution_label.config(state=DISABLED)
    resolution_dropdown = OptionMenu(file_type_frame,
                                     resolution_dropdown_selected, *resolution_list, command=set_resolution)
    resolution_dropdown.config(takefocus=1, font=("Arial", FontSize))
    resolution_dropdown.pack(side=LEFT)
    # resolution_dropdown.config(state=DISABLED)
    as_tooltips.add(resolution_dropdown, "Select the resolution to use when capturing the frames. Modes flagged with "
                                         "* are cropped, requiring lens adjustment")

    # File format (JPG or PNG)
    # Drop down to select file type
    # Dropdown menu options
    file_type_list = ["jpg", "png", "dng"]
    file_type_dropdown_selected = tk.StringVar()
    file_type_dropdown_selected.set(file_type_list[0])  # Set the initial value

    # No label for now
    file_type_label = Label(file_type_frame, text='Type:', font=("Arial", FontSize))
    # file_type_label.pack(side=LEFT)
    file_type_label.pack_forget()
    file_type_label.config(state=DISABLED)
    file_type_dropdown = OptionMenu(file_type_frame,
                                    file_type_dropdown_selected, *file_type_list, command=set_file_type)
    file_type_dropdown.config(takefocus=1, font=("Arial", FontSize))
    file_type_dropdown.pack(side=LEFT)
    # file_type_dropdown.config(state=DISABLED)
    as_tooltips.add(file_type_dropdown, "Select format to safe film frames (JPG or PNG)")

    top_right_area_row += 1

    # Create frame to display number of scanned images, and frames per minute
    scanned_images_frame = LabelFrame(top_right_area_frame, text='Scanned frames', height=4,
                                      font=("Arial", FontSize - 2))
    scanned_images_frame.grid(row=top_right_area_row, column=0, padx=x_pad, pady=y_pad, sticky='NSEW')

    Scanned_Images_number_str = tk.StringVar(value=str(CurrentFrame))
    Scanned_Images_number_label = Label(scanned_images_frame, textvariable=Scanned_Images_number_str,
                                        font=("Arial", FontSize + 6))
    Scanned_Images_number_label.pack(side=TOP)
    as_tooltips.add(Scanned_Images_number_label, "Number of film frames scanned so far.")

    scanned_images_fpm_frame = Frame(scanned_images_frame)
    scanned_images_fpm_frame.pack(side=TOP)
    Scanned_Images_time_str = tk.StringVar(value="Film time:")
    Scanned_Images_time_label = Label(scanned_images_fpm_frame, textvariable=Scanned_Images_time_str,
                                      font=("Arial", FontSize - 4))
    Scanned_Images_time_label.pack(side=BOTTOM)
    as_tooltips.add(Scanned_Images_time_label, "Film time in min:sec")

    Scanned_Images_Fpm_str = tk.StringVar(value="Frames/Min:")
    scanned_images_fpm_label = Label(scanned_images_fpm_frame, textvariable=Scanned_Images_Fpm_str,
                                     font=("Arial", FontSize - 4))
    scanned_images_fpm_label.pack(side=LEFT)
    as_tooltips.add(scanned_images_fpm_label, "Scan speed in frames per minute.")

    # Create frame to display number of frames to go, and estimated time to finish
    frames_to_go_frame = LabelFrame(top_right_area_frame, text='Frames to go', font=("Arial", FontSize - 2))
    frames_to_go_frame.grid(row=top_right_area_row, column=1, padx=x_pad, pady=y_pad, sticky='NSEW')
    top_right_area_row += 1

    frames_to_go_str = tk.StringVar(value='')
    frames_to_go_entry = tk.Entry(frames_to_go_frame, textvariable=frames_to_go_str, width=5, font=("Arial", FontSize),
                                  justify="right")
    # Bind the KeyRelease event to the entry widget
    frames_to_go_entry.bind("<KeyPress>", frames_to_go_key_press)
    frames_to_go_entry.pack(side=TOP)
    as_tooltips.add(frames_to_go_entry, "Enter estimated number of frames to scan in order to get an estimation of "
                                        "remaining time to finish.")
    time_to_go_str = tk.StringVar(value='')
    time_to_go_time = Label(frames_to_go_frame, textvariable=time_to_go_str, font=("Arial", FontSize - 4))
    time_to_go_time.pack(side=TOP)

    # Create frame to select S8/R8 film
    film_type_frame = LabelFrame(top_right_area_frame, text='Film type', height=1, font=("Arial", FontSize - 2))
    film_type_frame.grid(row=top_right_area_row, column=0, padx=x_pad, pady=y_pad, sticky='NSEW')

    # Radio buttons to select R8/S8. Required to select adequate pattern, and match position
    film_type = tk.StringVar()
    film_type_S8_rb = tk.Radiobutton(film_type_frame, text="S8", variable=film_type, command=set_s8,
                                     value='S8', font=("Arial", FontSize), indicatoron=0, width=5, height=2,
                                     compound='left', relief="raised", borderwidth=3)
    film_type_S8_rb.pack(side=LEFT)
    as_tooltips.add(film_type_S8_rb, "Handle as Super 8 film")
    film_type_R8_rb = tk.Radiobutton(film_type_frame, text="R8", variable=film_type, command=set_r8,
                                     value='R8', font=("Arial", FontSize), indicatoron=0, width=5, height=2,
                                     compound='left', relief="raised", borderwidth=3)
    film_type_R8_rb.pack(side=RIGHT)
    as_tooltips.add(film_type_R8_rb, "Handle as 8mm (Regular 8) film")

    # Create frame to display RPi temperature
    rpi_temp_frame = LabelFrame(top_right_area_frame, text='RPi Temp.', height=1, font=("Arial", FontSize - 2))
    rpi_temp_frame.grid(row=top_right_area_row, column=1, padx=x_pad, pady=y_pad, sticky='NSEW')
    temp_str = str(RPiTemp) + 'º'
    RPi_temp_value_label = Label(rpi_temp_frame, text=temp_str, font=("Arial", FontSize + 4))
    RPi_temp_value_label.pack(side=TOP)
    as_tooltips.add(RPi_temp_value_label, "Raspberry Pi Temperature.")

    temp_in_fahrenheit = tk.BooleanVar(value=False)
    temp_in_fahrenheit_checkbox = tk.Checkbutton(rpi_temp_frame, text='Fahrenheit', height=1,
                                                 variable=temp_in_fahrenheit, onvalue=True, offvalue=False,
                                                 command=temp_in_fahrenheit_selection, font=("Arial", FontSize))
    temp_in_fahrenheit_checkbox.pack(side=TOP)
    as_tooltips.add(temp_in_fahrenheit_checkbox, "Display Raspberry Pi Temperature in Fahrenheit.")
    top_right_area_row += 1

    # Integrated plotter
    if PlotterMode:
        integrated_plotter_frame = LabelFrame(top_right_area_frame, text='Plotter Area', font=("Arial", FontSize - 1))
        integrated_plotter_frame.grid(row=top_right_area_row, column=0, columnspan=2, padx=x_pad, pady=y_pad,
                                      ipadx=2, ipady=2, sticky='NSEW')
        plotter_canvas = Canvas(integrated_plotter_frame, bg='white', width=plotter_width, height=plotter_height)
        plotter_canvas.pack(side=TOP, anchor=N)
    top_right_area_row += 1

    # Create extended frame for expert and experimental areas
    if ExpertMode or ExperimentalMode:
        extended_frame = Frame(main_container)
        extended_frame.pack(side=LEFT, padx=10, expand=True, fill="y", anchor="center")
    if ExpertMode:
        expert_frame = LabelFrame(extended_frame, text='Expert Area', width=8, font=("Arial", FontSize - 1))
        expert_frame.pack(side=LEFT, padx=x_pad, pady=y_pad, expand=True, fill='y')
        # expert_frame.place(relx=0.25, rely=0.5, anchor="center")
        # *********************************
        # Exposure / white balance
        exp_wb_frame = LabelFrame(expert_frame, text='Auto Exposure / White Balance ', font=("Arial", FontSize - 1))
        exp_wb_frame.grid(row=0, rowspan=2, column=0, padx=x_pad, pady=y_pad, sticky='NSEW')
        exp_wb_row = 0

        catch_up_delay_label = tk.Label(exp_wb_frame, text='Match\nwait', font=("Arial", FontSize - 1))
        catch_up_delay_label.grid(row=exp_wb_row, column=2, sticky=W)
        exp_wb_row += 1

        # Automatic exposure
        AE_enabled = tk.BooleanVar(value=False)
        auto_exposure_btn = tk.Checkbutton(exp_wb_frame, variable=AE_enabled, onvalue=True, offvalue=False,
                                           font=("Arial", FontSize - 1), command=set_auto_exposure, indicatoron=False,
                                           selectcolor="pale green", text="Exposure:", relief="raised")
        auto_exposure_btn.grid(row=exp_wb_row, column=0, sticky="EW")
        as_tooltips.add(auto_exposure_btn, "Toggle automatic exposure status (on/off).")

        exposure_value = tk.DoubleVar(value=0)  # Auto exposure by default, overriden by configuration if any
        exposure_spinbox = DynamicSpinbox(exp_wb_frame, command=exposure_selection, width=8,
                                          textvariable=exposure_value,
                                          from_=0.001, to=10000, increment=1, font=("Arial", FontSize - 1))
        exposure_spinbox.grid(row=exp_wb_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        exposure_validation_cmd = exposure_spinbox.register(exposure_validation)
        exposure_spinbox.configure(validate="key", validatecommand=(exposure_validation_cmd, '%P'))
        as_tooltips.add(exposure_spinbox, "When automatic exposure disabled, exposure time for the sensor to use, "
                                          "measured in milliseconds.")
        exposure_spinbox.bind("<FocusOut>", lambda event: exposure_selection())

        auto_exposure_change_pause = tk.BooleanVar(value=True)  # Default value, to be overriden by configuration
        auto_exposure_wait_btn = tk.Checkbutton(exp_wb_frame, state=DISABLED, variable=auto_exposure_change_pause,
                                                onvalue=True, offvalue=False, font=("Arial", FontSize - 1),
                                                command=auto_exposure_change_pause_selection)
        auto_exposure_wait_btn.grid(row=exp_wb_row, column=2, sticky=W)
        as_tooltips.add(auto_exposure_wait_btn, "When automatic exposure enabled, select to wait for it to stabilize "
                                                "before capturing frame.")
        exp_wb_row += 1

        # Automatic White Balance red
        AWB_enabled = tk.BooleanVar(value=False)
        auto_wb_red_btn = tk.Checkbutton(exp_wb_frame, variable=AWB_enabled, onvalue=True, offvalue=False,
                                         font=("Arial", FontSize - 1), command=set_auto_wb, selectcolor="pale green",
                                         text="WB Red:", relief="raised", indicatoron=False)
        auto_wb_red_btn.grid(row=exp_wb_row, column=0, sticky="WE")
        as_tooltips.add(auto_wb_red_btn, "Toggle automatic white balance for both WB channels (on/off).")

        wb_red_value = tk.DoubleVar(value=2.2)  # Default value, overriden by configuration
        wb_red_spinbox = DynamicSpinbox(exp_wb_frame, command=wb_red_selection, width=8,
                                        textvariable=wb_red_value, from_=0, to=32, increment=0.1,
                                        font=("Arial", FontSize - 1))
        wb_red_spinbox.grid(row=exp_wb_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        wb_red_validation_cmd = wb_red_spinbox.register(wb_red_validation)
        wb_red_spinbox.configure(validate="key", validatecommand=(wb_red_validation_cmd, '%P'))
        as_tooltips.add(wb_red_spinbox, "When automatic white balance disabled, sets the red gain (the gain applied "
                                        "to red pixels by the AWB algorithm), between 0.0 to 32.0.")
        wb_red_spinbox.bind("<FocusOut>", lambda event: wb_red_selection())

        auto_white_balance_change_pause = tk.BooleanVar(value=False)
        auto_wb_wait_btn = tk.Checkbutton(exp_wb_frame, state=DISABLED, variable=auto_white_balance_change_pause,
                                          onvalue=True, offvalue=False, font=("Arial", FontSize - 1),
                                          command=auto_white_balance_change_pause_selection)
        auto_wb_wait_btn.grid(row=exp_wb_row, rowspan=2, column=2, sticky=W)
        as_tooltips.add(auto_wb_wait_btn, "When automatic white balance enabled, select to wait for it to stabilize "
                                          "before capturing frame.")
        exp_wb_row += 1

        # Automatic White Balance blue
        auto_wb_blue_btn = tk.Checkbutton(exp_wb_frame, variable=AWB_enabled, onvalue=True, offvalue=False,
                                          font=("Arial", FontSize - 1), command=set_auto_wb, selectcolor="pale green",
                                          text="WB Blue:", relief="raised", indicatoron=False)
        auto_wb_blue_btn.grid(row=exp_wb_row, column=0, sticky="WE")
        as_tooltips.add(auto_wb_blue_btn, "Toggle automatic white balance for both WB channels (on/off).")

        wb_blue_value = tk.DoubleVar(value=2.2)  # Default value, overriden by configuration
        wb_blue_spinbox = DynamicSpinbox(exp_wb_frame, command=wb_blue_selection, width=8,
                                         textvariable=wb_blue_value, from_=0, to=32, increment=0.1,
                                         font=("Arial", FontSize - 1))
        wb_blue_spinbox.grid(row=exp_wb_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        wb_blue_validation_cmd = wb_blue_spinbox.register(wb_blue_validation)
        wb_blue_spinbox.configure(validate="key", validatecommand=(wb_blue_validation_cmd, '%P'))
        as_tooltips.add(wb_blue_spinbox, "When automatic white balance disabled, sets the blue gain (the gain applied "
                                         "to blue pixels by the AWB algorithm), between 0.0 to 32.0.")
        wb_blue_spinbox.bind("<FocusOut>", lambda event: wb_blue_selection())

        exp_wb_row += 1

        # Match wait (exposure & AWB) margin allowance (0%, wait for same value, 100%, any value will do)
        match_wait_margin_label = tk.Label(exp_wb_frame, text='Match margin (%):', font=("Arial", FontSize - 1))
        match_wait_margin_label.grid(row=exp_wb_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        match_wait_margin_value = tk.IntVar(value=50)  # Default value, overriden by configuration
        match_wait_margin_spinbox = DynamicSpinbox(exp_wb_frame, command=match_wait_margin_selection, width=8,
                                                   readonlybackground='pale green', from_=5, to=100, increment=5,
                                                   textvariable=match_wait_margin_value, font=("Arial", FontSize - 1))
        match_wait_margin_spinbox.grid(row=exp_wb_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        match_wait_margin_validation_cmd = match_wait_margin_spinbox.register(match_wait_margin_validation)
        match_wait_margin_spinbox.configure(validate="key", validatecommand=(match_wait_margin_validation_cmd, '%P'))
        as_tooltips.add(match_wait_margin_spinbox, "When automatic exposure/WB enabled, and match wait delay is "
                                                   "selected, the tolerance for the match (5%, lowest tolerance, "
                                                   "almost exact match required, 100% any value will match)")
        match_wait_margin_spinbox.bind("<FocusOut>", lambda event: match_wait_margin_selection())
        exp_wb_row += 1

        # Miscelaneous exposure controls from PiCamera2 - AeConstraintMode
        AeConstraintMode_dropdown_selected = tk.StringVar()
        AeConstraintMode_dropdown_selected.set("Normal")  # Set the initial value
        AeConstraintMode_label = Label(exp_wb_frame, text='AE Const. mode:', font=("Arial", FontSize - 1),
                                       state=DISABLED)
        AeConstraintMode_label.grid(row=exp_wb_row, column=0, padx=x_pad, pady=y_pad, sticky=E)
        AeConstraintMode_dropdown = OptionMenu(exp_wb_frame, AeConstraintMode_dropdown_selected,
                                               *AeConstraintMode_dict.keys(), command=set_AeConstraintMode)
        AeConstraintMode_dropdown.config(takefocus=1, font=("Arial", FontSize - 1), state=DISABLED)
        AeConstraintMode_dropdown.grid(row=exp_wb_row, columnspan=2, column=1, padx=x_pad, pady=y_pad, sticky=W)
        as_tooltips.add(AeConstraintMode_dropdown, "Sets the constraint mode of the AEC/AGC algorithm.")
        exp_wb_row += 1

        # Miscelaneous exposure controls from PiCamera2 - AeMeteringMode
        # camera.set_controls({"AeMeteringMode": controls.AeMeteringModeEnum.CentreWeighted})
        AeMeteringMode_dropdown_selected = tk.StringVar()
        AeMeteringMode_dropdown_selected.set("CentreWeighted")  # Set the initial value
        AeMeteringMode_label = Label(exp_wb_frame, text='AE Meter mode:', font=("Arial", FontSize - 1), state=DISABLED)
        AeMeteringMode_label.grid(row=exp_wb_row, column=0, padx=x_pad, pady=y_pad, sticky=E)
        AeMeteringMode_dropdown = OptionMenu(exp_wb_frame, AeMeteringMode_dropdown_selected,
                                             *AeMeteringMode_dict.keys(), command=set_AeMeteringMode)
        AeMeteringMode_dropdown.config(takefocus=1, font=("Arial", FontSize - 1), state=DISABLED)
        AeMeteringMode_dropdown.grid(row=exp_wb_row, columnspan=2, column=1, padx=x_pad, pady=y_pad, sticky=W)
        as_tooltips.add(AeMeteringMode_dropdown, "Sets the metering mode of the AEC/AGC algorithm.")
        exp_wb_row += 1

        # Miscelaneous exposure controls from PiCamera2 - AeExposureMode
        # camera.set_controls({"AeExposureMode": controls.AeExposureModeEnum.Normal})  # Normal, Long, Short, Custom
        AeExposureMode_dropdown_selected = tk.StringVar()
        AeExposureMode_dropdown_selected.set("Normal")  # Set the initial value
        AeExposureMode_label = Label(exp_wb_frame, text='AE Exposure mode:', font=("Arial", FontSize - 1),
                                     state=DISABLED)
        AeExposureMode_label.grid(row=exp_wb_row, column=0, padx=x_pad, pady=y_pad, sticky=E)
        AeExposureMode_dropdown = OptionMenu(exp_wb_frame, AeExposureMode_dropdown_selected,
                                             *AeExposureMode_dict.keys(), command=set_AeExposureMode)
        AeExposureMode_dropdown.config(takefocus=1, font=("Arial", FontSize - 1), state=DISABLED)
        AeExposureMode_dropdown.grid(row=exp_wb_row, columnspan=2, column=1, padx=x_pad, pady=y_pad, sticky=W)
        as_tooltips.add(AeExposureMode_dropdown, "Sets the exposure mode of the AEC/AGC algorithm.")
        exp_wb_row += 1

        # Miscelaneous exposure controls from PiCamera2 - AwbMode
        # camera.set_controls({"AwbMode": controls.AwbModeEnum.Normal})  # Normal, Long, Short, Custom
        AwbMode_dropdown_selected = tk.StringVar()
        AwbMode_dropdown_selected.set("Normal")  # Set the initial value
        AwbMode_label = Label(exp_wb_frame, text='AWB mode:', font=("Arial", FontSize - 1), state=DISABLED)
        AwbMode_label.grid(row=exp_wb_row, column=0, padx=x_pad, pady=y_pad, sticky=E)
        AwbMode_dropdown = OptionMenu(exp_wb_frame, AwbMode_dropdown_selected,
                                      *AwbMode_dict.keys(), command=set_AwbMode)
        AwbMode_dropdown.config(takefocus=1, font=("Arial", FontSize - 1), state=DISABLED)
        AwbMode_dropdown.grid(row=exp_wb_row, columnspan=2, column=1, padx=x_pad, pady=y_pad, sticky=W)
        as_tooltips.add(AwbMode_dropdown, "Sets the AWB mode of the AEC/AGC algorithm.")
        exp_wb_row += 1

        # *****************************************
        # Frame to add brightness/contrast controls
        brightness_frame = LabelFrame(expert_frame, text="Brightness/Contrast", font=("Arial", FontSize - 1))
        brightness_frame.grid(row=0, column=1, padx=x_pad, pady=y_pad, sticky='NSEW')
        brightness_row = 0

        # brightness
        brightness_label = tk.Label(brightness_frame, text='Brightness:', font=("Arial", FontSize - 1))
        brightness_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        brightness_value = tk.DoubleVar(value=0.0)  # Default value, overriden by configuration
        brightness_spinbox = DynamicSpinbox(brightness_frame, command=brightness_selection, width=8,
                                            textvariable=brightness_value, from_=-1.0, to=1.0, increment=0.1,
                                            font=("Arial", FontSize - 1))
        brightness_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        brightness_validation_cmd = brightness_spinbox.register(brightness_validation)
        brightness_spinbox.configure(validate="key", validatecommand=(brightness_validation_cmd, '%P'))
        as_tooltips.add(brightness_spinbox, 'Adjusts the image brightness between -1.0 and 1.0, where -1.0 is very '
                                            'dark, 1.0 is very bright, and 0.0 is the default "normal" brightness.')
        brightness_spinbox.bind("<FocusOut>", lambda event: brightness_selection())
        brightness_row += 1

        # contrast
        contrast_label = tk.Label(brightness_frame, text='Contrast:', font=("Arial", FontSize - 1))
        contrast_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        contrast_value = tk.DoubleVar(value=1)  # Default value, overriden by configuration
        contrast_spinbox = DynamicSpinbox(brightness_frame, command=contrast_selection, width=8,
                                          textvariable=contrast_value, from_=0, to=32, increment=0.1,
                                          font=("Arial", FontSize - 1))
        contrast_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        contrast_validation_cmd = contrast_spinbox.register(contrast_validation)
        contrast_spinbox.configure(validate="key", validatecommand=(contrast_validation_cmd, '%P'))
        as_tooltips.add(contrast_spinbox, 'Sets the contrast of the image between 0.0 and 32.0, where zero means "no '
                                          'contrast", 1.0 is the default "normal" contrast, and larger values '
                                          'increase the contrast proportionately.')
        contrast_spinbox.bind("<FocusOut>", lambda event: contrast_selection())
        brightness_row += 1

        # saturation
        saturation_label = tk.Label(brightness_frame, text='Saturation:', font=("Arial", FontSize - 1))
        saturation_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        saturation_value = tk.DoubleVar(value=1)  # Default value, overriden by configuration
        saturation_spinbox = DynamicSpinbox(brightness_frame, command=saturation_selection, width=8,
                                            textvariable=saturation_value, from_=0, to=32, increment=0.1,
                                            font=("Arial", FontSize - 1))
        saturation_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        saturation_validation_cmd = saturation_spinbox.register(saturation_validation)
        saturation_spinbox.configure(validate="key", validatecommand=(saturation_validation_cmd, '%P'))
        as_tooltips.add(saturation_spinbox, 'Amount of colour saturation between 0.0 and 32.0, where zero produces '
                                            'greyscale images, 1.0 represents default "normal" saturation, '
                                            'and higher values produce more saturated colours.')
        saturation_spinbox.bind("<FocusOut>", lambda event: saturation_selection())
        brightness_row += 1

        # analogue_gain
        analogue_gain_label = tk.Label(brightness_frame, text='Analog. gain:', font=("Arial", FontSize - 1))
        analogue_gain_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        analogue_gain_value = tk.DoubleVar(value=1)  # Default value, overriden by configuration
        analogue_gain_spinbox = DynamicSpinbox(brightness_frame, command=analogue_gain_selection, width=8,
                                               textvariable=analogue_gain_value, from_=0, to=32, increment=0.1,
                                               font=("Arial", FontSize - 1))
        analogue_gain_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        analogue_gain_validation_cmd = analogue_gain_spinbox.register(analogue_gain_validation)
        analogue_gain_spinbox.configure(validate="key", validatecommand=(analogue_gain_validation_cmd, '%P'))
        as_tooltips.add(analogue_gain_spinbox, "Analogue gain applied by the sensor.")
        analogue_gain_spinbox.bind("<FocusOut>", lambda event: analogue_gain_selection())
        brightness_row += 1

        # Sharpness, control to allow playing with the values and see the results
        sharpness_label = tk.Label(brightness_frame, text='Sharpness:', font=("Arial", FontSize - 1))
        sharpness_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        sharpness_value = tk.DoubleVar(value=1)  # Default value, overridden by configuration if any
        sharpness_spinbox = DynamicSpinbox(brightness_frame, command=sharpness_selection, width=8,
                                           textvariable=sharpness_value, from_=0.0, to=16.0, increment=1,
                                           font=("Arial", FontSize - 1))
        sharpness_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        sharpness_validation_cmd = sharpness_spinbox.register(sharpness_validation)
        sharpness_spinbox.configure(validate="key", validatecommand=(sharpness_validation_cmd, '%P'))
        as_tooltips.add(sharpness_spinbox, 'Sets the image sharpness between 0.0 adn 16.0, where zero implies no '
                                           'additional sharpening is performed, 1.0 is the default "normal" level of '
                                           'sharpening, and larger values apply proportionately stronger sharpening.')
        sharpness_spinbox.bind("<FocusOut>", lambda event: sharpness_selection())
        brightness_row += 1

        # Exposure Compensation ('ExposureValue' in PiCamera2 controls
        exposure_compensation_label = tk.Label(brightness_frame, text='Exp. Comp.:', font=("Arial", FontSize - 1))
        exposure_compensation_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        exposure_compensation_value = tk.DoubleVar(value=0)  # Default value, overridden by configuration if any
        exposure_compensation_spinbox = DynamicSpinbox(brightness_frame, command=exposure_compensation_selection,
                                                       width=8, textvariable=exposure_compensation_value, from_=-8.0,
                                                       to=8.0, increment=0.1, font=("Arial", FontSize - 1))
        exposure_compensation_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        exposure_compensation_validation_cmd = exposure_compensation_spinbox.register(exposure_compensation_validation)
        exposure_compensation_spinbox.configure(validate="key",
                                                validatecommand=(exposure_compensation_validation_cmd, '%P'))
        as_tooltips.add(exposure_compensation_spinbox, 'Exposure compensation value in "stops" (-8.0 to 8.0), which '
                                                       'adjusts the target of the AEC/AGC algorithm. Positive values '
                                                       'increase the target brightness, and negative values decrease '
                                                       'it. Zero represents the base or "normal" exposure level.')
        exposure_compensation_spinbox.bind("<FocusOut>", lambda event: exposure_compensation_selection())

        # *********************************
        # Frame to add frame align controls
        frame_alignment_frame = LabelFrame(expert_frame, text="Frame align", font=("Arial", FontSize - 1))
        frame_alignment_frame.grid(row=0, column=2, padx=x_pad, pady=y_pad, sticky='NSEW')
        frame_align_row = 0

        # Spinbox to select MinFrameSteps on Arduino
        auto_framesteps_enabled = tk.BooleanVar(value=True)
        steps_per_frame_btn = tk.Checkbutton(frame_alignment_frame, variable=auto_framesteps_enabled, onvalue=True,
                                             offvalue=False, font=("Arial", FontSize - 1), command=steps_per_frame_auto,
                                             selectcolor="pale green", text="Steps/Frame AUTO:", relief="raised",
                                             indicatoron=False, width=18)
        steps_per_frame_btn.grid(row=frame_align_row, column=0, sticky="EW")
        as_tooltips.add(steps_per_frame_btn, "Toggle automatic steps/frame calculation.")

        steps_per_frame_value = tk.IntVar(value=250)  # Default to be overridden by configuration
        steps_per_frame_spinbox = DynamicSpinbox(frame_alignment_frame, command=steps_per_frame_selection, width=4,
                                                 textvariable=steps_per_frame_value, from_=100, to=600,
                                                 font=("Arial", FontSize - 1))
        steps_per_frame_spinbox.grid(row=frame_align_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        steps_per_frame_validation_cmd = steps_per_frame_spinbox.register(steps_per_frame_validation)
        steps_per_frame_spinbox.configure(validate="key", validatecommand=(steps_per_frame_validation_cmd, '%P'))
        as_tooltips.add(steps_per_frame_spinbox, "If automatic steps/frame is disabled, enter the number of motor "
                                                 "steps required to advance one frame (100 to 600, depends on capstan"
                                                 " diameter).")
        steps_per_frame_spinbox.bind("<FocusOut>", lambda event: steps_per_frame_selection())

        frame_align_row += 1

        # Spinbox to select PTLevel on Arduino
        auto_pt_level_enabled = tk.BooleanVar(value=True)
        pt_level_btn = tk.Checkbutton(frame_alignment_frame, variable=auto_pt_level_enabled, onvalue=True,
                                      offvalue=False, font=("Arial", FontSize - 1), command=set_auto_pt_level,
                                      selectcolor="pale green", text="PT Level AUTO:", relief="raised",
                                      indicatoron=False)
        pt_level_btn.grid(row=frame_align_row, column=0, sticky="EW")
        as_tooltips.add(pt_level_btn, "Toggle automatic photo-transistor level calculation.")

        pt_level_value = tk.IntVar(value=200)  # To be overridden by config
        pt_level_spinbox = DynamicSpinbox(frame_alignment_frame, command=pt_level_selection, width=4,
                                          textvariable=pt_level_value, from_=20, to=900, font=("Arial", FontSize - 1))
        pt_level_spinbox.grid(row=frame_align_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        pt_level_validation_cmd = pt_level_spinbox.register(pt_level_validation)
        pt_level_spinbox.configure(validate="key", validatecommand=(pt_level_validation_cmd, '%P'))
        as_tooltips.add(pt_level_spinbox, "If automatic photo-transistor is disabled, enter the level to be reached "
                                          "to determine detection of sprocket hole (20 to 900, depends on PT used and"
                                          " size of hole).")
        pt_level_spinbox.bind("<FocusOut>", lambda event: pt_level_selection())

        frame_align_row += 1

        # Spinbox to select Frame Fine Tune on Arduino
        frame_fine_tune_label = tk.Label(frame_alignment_frame, text='Fine tune:', font=("Arial", FontSize - 1))
        frame_fine_tune_label.grid(row=frame_align_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        frame_fine_tune_value = tk.IntVar(value=50)  # To be overridden by config
        frame_fine_tune_spinbox = DynamicSpinbox(frame_alignment_frame, command=frame_fine_tune_selection, width=4,
                                                 readonlybackground='pale green', textvariable=frame_fine_tune_value,
                                                 from_=5, to=95, increment=5, font=("Arial", FontSize - 1))
        frame_fine_tune_spinbox.grid(row=frame_align_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        fine_tune_validation_cmd = frame_fine_tune_spinbox.register(fine_tune_validation)
        frame_fine_tune_spinbox.configure(validate="key", validatecommand=(fine_tune_validation_cmd, '%P'))
        as_tooltips.add(frame_fine_tune_spinbox, "Fine tune frame detection: Shift frame detection threshold up of "
                                                 "down (5 to 95% of PT amplitude).")
        frame_fine_tune_spinbox.bind("<FocusOut>", lambda event: frame_fine_tune_selection())
        frame_align_row += 1

        # Spinbox to select Extra Steps on Arduino
        frame_extra_steps_label = tk.Label(frame_alignment_frame, text='Extra Steps:', font=("Arial", FontSize - 1))
        frame_extra_steps_label.grid(row=frame_align_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        frame_extra_steps_value = tk.IntVar(value=0)  # To be overridden by config
        frame_extra_steps_spinbox = DynamicSpinbox(frame_alignment_frame, command=frame_extra_steps_selection, width=4,
                                                   readonlybackground='pale green', from_=-30, to=30,
                                                   textvariable=frame_extra_steps_value, font=("Arial", FontSize - 1))
        frame_extra_steps_spinbox.grid(row=frame_align_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        extra_steps_validation_cmd = frame_extra_steps_spinbox.register(extra_steps_validation)
        frame_extra_steps_spinbox.configure(validate="key", validatecommand=(extra_steps_validation_cmd, '%P'))
        as_tooltips.add(frame_extra_steps_spinbox, "Unconditionally advances/detects the frame n steps after/before "
                                                   "detection (n between -30 and 30). Negative values can help if "
                                                   "film gate is not correctly positioned.")
        frame_extra_steps_spinbox.bind("<FocusOut>", lambda event: frame_extra_steps_selection())

        # ***************************************************
        # Frame to add stabilization controls (speed & delay)
        speed_quality_frame = LabelFrame(expert_frame, text="Frame stabilization", font=("Arial", FontSize - 1))
        speed_quality_frame.grid(row=1, column=2, padx=x_pad, pady=y_pad, sticky='NSEW')

        # Spinbox to select Speed on Arduino (1-10)
        scan_speed_label = tk.Label(speed_quality_frame, text='Scan Speed:', font=("Arial", FontSize - 1))
        scan_speed_label.grid(row=0, column=0, padx=x_pad, pady=y_pad, sticky=E)
        scan_speed_value = tk.IntVar(value=5)  # Default value, overriden by configuration
        scan_speed_spinbox = DynamicSpinbox(speed_quality_frame, command=scan_speed_selection, width=4,
                                            textvariable=scan_speed_value, from_=1, to=10, font=("Arial", FontSize - 1))
        scan_speed_spinbox.grid(row=0, column=1, padx=x_pad, pady=y_pad, sticky=W)
        scan_speed_validation_cmd = scan_speed_spinbox.register(scan_speed_validation)
        scan_speed_spinbox.configure(validate="key", validatecommand=(scan_speed_validation_cmd, '%P'))
        as_tooltips.add(scan_speed_spinbox, "Select scan speed from 1 (slowest) to 10 (fastest).A speed of 5 is "
                                            "usually a good compromise between speed and good frame position "
                                            "detection.")
        scan_speed_spinbox.bind("<FocusOut>", lambda event: scan_speed_selection())

        # Display entry to adjust capture stabilization delay (100 ms by default)
        stabilization_delay_label = tk.Label(speed_quality_frame, text='Stabilization\ndelay (ms):',
                                             font=("Arial", FontSize - 1))
        stabilization_delay_label.grid(row=1, column=0, padx=x_pad, pady=y_pad, sticky=E)
        stabilization_delay_value = tk.IntVar(value=100)  # default value, overriden by configuration
        stabilization_delay_spinbox = DynamicSpinbox(speed_quality_frame, command=stabilization_delay_selection,
                                                     width=4, textvariable=stabilization_delay_value, from_=0, to=1000,
                                                     increment=10, font=("Arial", FontSize - 1))
        stabilization_delay_spinbox.grid(row=1, column=1, padx=x_pad, pady=y_pad, sticky=W)
        stabilization_delay_validation_cmd = stabilization_delay_spinbox.register(stabilization_delay_validation)
        stabilization_delay_spinbox.configure(validate="key",
                                              validatecommand=(stabilization_delay_validation_cmd, '%P'))
        as_tooltips.add(stabilization_delay_spinbox, "Delay between frame detection and snapshot trigger. 100ms is a "
                                                     "good compromise, lower values might cause blurry captures.")
        stabilization_delay_spinbox.bind("<FocusOut>", lambda event: stabilization_delay_selection())

    if ExperimentalMode:
        experimental_frame = LabelFrame(extended_frame, text='Experimental Area', font=("Arial", FontSize - 1))
        experimental_frame.pack(side=LEFT, padx=x_pad, pady=y_pad, expand=True, fill='y')
        # experimental_frame.place(relx=0.75, rely=0.5, anchor="center")

        # Frame to add HDR controls (on/off, exp. bracket, position, auto-adjust)
        hdr_frame = LabelFrame(experimental_frame, text="Multi-exposure fusion", font=("Arial", FontSize - 1))
        hdr_frame.pack(side=LEFT, fill='both', padx=x_pad, pady=y_pad, expand=True)
        hdr_row = 0
        hdr_capture_active = tk.BooleanVar(value=HdrCaptureActive)
        hdr_capture_active_checkbox = tk.Checkbutton(hdr_frame, text=' Active', height=1,
                                                     variable=hdr_capture_active, onvalue=True, offvalue=False,
                                                     command=switch_hdr_capture, font=("Arial", FontSize - 1))
        hdr_capture_active_checkbox.grid(row=hdr_row, column=0, sticky=W)
        as_tooltips.add(hdr_capture_active_checkbox, "Activate multi-exposure scan. Three snapshots of each frame "
                                                     "will be taken with different exposures, to be merged later by "
                                                     "AfterScan.")
        hdr_viewx4_active = tk.BooleanVar(value=HdrViewX4Active)
        hdr_viewx4_active_checkbox = tk.Checkbutton(hdr_frame, text=' View X4', height=1, variable=hdr_viewx4_active,
                                                    onvalue=True, offvalue=False, command=switch_hdr_viewx4,
                                                    font=("Arial", FontSize - 1), state=DISABLED)
        hdr_viewx4_active_checkbox.grid(row=hdr_row, column=1, sticky=W)
        as_tooltips.add(hdr_viewx4_active_checkbox, "Alternate frame display during capture. Instead of displaying a "
                                                    "single frame (the one in the middle), all three frames will be "
                                                    "displayed sequentially.")
        hdr_row += 1

        hdr_min_exp_label = tk.Label(hdr_frame, text='Lower exp. (ms):', font=("Arial", FontSize - 1), state=DISABLED)
        hdr_min_exp_label.grid(row=hdr_row, column=0, padx=x_pad, pady=y_pad, sticky=E)
        hdr_min_exp_value = tk.IntVar(value=hdr_lower_exp)
        hdr_min_exp_spinbox = DynamicSpinbox(hdr_frame, command=hdr_min_exp_selection, width=8, state=DISABLED,
                                             readonlybackground='pale green', textvariable=hdr_min_exp_value,
                                             from_=hdr_lower_exp, to=999, increment=1, font=("Arial", FontSize - 1))
        hdr_min_exp_spinbox.grid(row=hdr_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        hdr_min_exp_validation_cmd = hdr_min_exp_spinbox.register(hdr_min_exp_validation)
        hdr_min_exp_spinbox.configure(validate="key", validatecommand=(hdr_min_exp_validation_cmd, '%P'))
        as_tooltips.add(hdr_min_exp_spinbox, "When multi-exposure enabled, lower value of the exposure bracket.")
        hdr_min_exp_spinbox.bind("<FocusOut>", lambda event: hdr_min_exp_selection())
        hdr_row += 1

        hdr_max_exp_label = tk.Label(hdr_frame, text='Higher exp. (ms):', font=("Arial", FontSize - 1), state=DISABLED)
        hdr_max_exp_label.grid(row=hdr_row, column=0, padx=x_pad, pady=y_pad, sticky=E)
        hdr_max_exp_value = tk.IntVar(value=hdr_higher_exp)
        hdr_max_exp_spinbox = DynamicSpinbox(hdr_frame, command=hdr_max_exp_selection, width=8, from_=2, to=1000,
                                             readonlybackground='pale green', textvariable=hdr_max_exp_value,
                                             increment=1, font=("Arial", FontSize - 1), state=DISABLED)
        hdr_max_exp_spinbox.grid(row=hdr_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        hdr_max_exp_validation_cmd = hdr_max_exp_spinbox.register(hdr_max_exp_validation)
        hdr_max_exp_spinbox.configure(validate="key", validatecommand=(hdr_max_exp_validation_cmd, '%P'))
        as_tooltips.add(hdr_max_exp_spinbox, "When multi-exposure enabled, upper value of the exposure bracket.")
        hdr_max_exp_spinbox.bind("<FocusOut>", lambda event: hdr_max_exp_selection())
        hdr_row += 1

        hdr_bracket_width_label = tk.Label(hdr_frame, text='Bracket width (ms):', font=("Arial", FontSize - 1),
                                           state=DISABLED)
        hdr_bracket_width_label.grid(row=hdr_row, column=0, padx=x_pad, pady=y_pad, sticky=E)
        hdr_bracket_width_value = tk.IntVar(value=50)
        hdr_bracket_width_spinbox = DynamicSpinbox(hdr_frame, command=hdr_bracket_width_selection, width=8,
                                                   textvariable=hdr_bracket_width_value, from_=hdr_min_bracket_width,
                                                   to=hdr_max_bracket_width, increment=1, font=("Arial", FontSize - 1),
                                                   state=DISABLED)
        hdr_bracket_width_spinbox.grid(row=hdr_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        hdr_bracket_width_validation_cmd = hdr_bracket_width_spinbox.register(hdr_bracket_width_validation)
        hdr_bracket_width_spinbox.configure(validate="key", validatecommand=(hdr_bracket_width_validation_cmd, '%P'))
        as_tooltips.add(hdr_bracket_width_spinbox, "When multi-exposure enabled, width of the exposure bracket ("
                                                   "useful for automatic mode).")
        hdr_bracket_width_spinbox.bind("<FocusOut>", lambda event: hdr_bracket_width_selection())
        hdr_row += 1

        hdr_bracket_shift_label = tk.Label(hdr_frame, text='Bracket shift (ms):', font=("Arial", FontSize - 1),
                                           state=DISABLED)
        hdr_bracket_shift_label.grid(row=hdr_row, column=0, padx=x_pad, pady=y_pad, sticky=E)
        hdr_bracket_shift_value = tk.IntVar(value=0)
        hdr_bracket_shift_spinbox = DynamicSpinbox(hdr_frame, command=hdr_bracket_shift_selection, width=8,
                                                   textvariable=hdr_bracket_shift_value, from_=-100, to=100,
                                                   increment=10, font=("Arial", FontSize - 1), state=DISABLED)
        hdr_bracket_shift_spinbox.grid(row=hdr_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        hdr_bracket_shift_validation_cmd = hdr_bracket_shift_spinbox.register(hdr_bracket_shift_validation)
        hdr_bracket_shift_spinbox.configure(validate="key", validatecommand=(hdr_bracket_shift_validation_cmd, '%P'))
        as_tooltips.add(hdr_bracket_shift_spinbox, "When multi-exposure enabled, shift exposure bracket up or down "
                                                   "from default position.")
        hdr_bracket_shift_spinbox.bind("<FocusOut>", lambda event: hdr_bracket_shift_selection())
        hdr_row += 1

        hdr_bracket_auto = tk.BooleanVar(value=False)
        hdr_bracket_width_auto_checkbox = tk.Checkbutton(hdr_frame, text='Auto bracket', height=1,
                                                         variable=hdr_bracket_auto, onvalue=True, offvalue=False,
                                                         command=adjust_hdr_bracket_auto, font=("Arial", FontSize - 1))
        hdr_bracket_width_auto_checkbox.grid(row=hdr_row, column=0, sticky=W)
        as_tooltips.add(hdr_bracket_width_auto_checkbox, "Enable automatic multi-exposure: For each frame, ALT-Scann8 "
                                                         "will retrieve the auto-exposure level reported by the RPi "
                                                         "HQ camera, adn will use it for the middle exposure, "
                                                         "calculating the lower/upper values according to the bracket "
                                                         "defined.")
        hdr_row += 1

        hdr_merge_in_place = tk.BooleanVar(value=False)
        hdr_merge_in_place_checkbox = tk.Checkbutton(hdr_frame, text='Merge in place', height=1,
                                                     variable=hdr_merge_in_place, onvalue=True, offvalue=False,
                                                     command=adjust_merge_in_place, font=("Arial", FontSize - 1))
        hdr_merge_in_place_checkbox.grid(row=hdr_row, column=0, sticky=W)
        as_tooltips.add(hdr_merge_in_place_checkbox, "Enable to perform Mertens merge on the Raspberry Pi, while "
                                                     "encoding. Allow to make some use of the time spent waiting for "
                                                     "the camera to adapt the exposure.")

        # Experimental miscellaneous sub-frame
        experimental_miscellaneous_frame = LabelFrame(experimental_frame, text='Miscellaneous',
                                                      font=("Arial", FontSize - 1))
        experimental_miscellaneous_frame.pack(side=LEFT, padx=x_pad, pady=y_pad, fill='both', expand=True)

        # Display entry to throttle Rwnd/FF speed
        rwnd_speed_control_label = tk.Label(experimental_miscellaneous_frame, text='RW/FF speed:',
                                            font=("Arial", FontSize - 1))
        rwnd_speed_control_label.grid(row=0, column=0, padx=x_pad, pady=y_pad)
        rwnd_speed_control_value = tk.IntVar(value=round(60 / (rwnd_speed_delay * 375 / 1000000)))
        rwnd_speed_control_spinbox = DynamicSpinbox(experimental_miscellaneous_frame, state='readonly', width=4,
                                                    command=rwnd_speed_control_selection, from_=40, to=800,
                                                    increment=50,
                                                    textvariable=rwnd_speed_control_value, font=("Arial", FontSize - 1))
        rwnd_speed_control_spinbox.grid(row=0, column=1, padx=x_pad, pady=y_pad)
        rewind_speed_validation_cmd = rwnd_speed_control_spinbox.register(rewind_speed_validation)
        rwnd_speed_control_spinbox.configure(validate="key", validatecommand=(rewind_speed_validation_cmd, '%P'))
        as_tooltips.add(rwnd_speed_control_spinbox, "Speed up/slow down the RWND/FF speed.")
        # No need to validate on FocusOut, since no keyboard entry is allowed in this one

        # Damaged film helpers, to help handling damaged film (broken perforations)
        Damaged_film_frame = LabelFrame(experimental_miscellaneous_frame, text='Damaged film',
                                        font=("Arial", FontSize - 1))
        Damaged_film_frame.grid(row=1, column=0, columnspan=2, padx=x_pad, pady=y_pad)
        # Checkbox to enable/disable manual scan
        Manual_scan_activated = tk.BooleanVar(value=ManualScanEnabled)
        Manual_scan_checkbox = tk.Checkbutton(Damaged_film_frame, text='Enable manual scan',
                                              variable=Manual_scan_activated, onvalue=True,
                                              offvalue=False,
                                              command=Manual_scan_activated_selection, font=("Arial", FontSize - 1))
        Manual_scan_checkbox.pack(side=TOP)
        as_tooltips.add(Manual_scan_checkbox, "Enable manual scan (for films with very damaged sprocket holes). Lots "
                                              "of manual work, use it if everything else fails.")
        # Common area for buttons
        Manual_scan_btn_frame = Frame(Damaged_film_frame)
        Manual_scan_btn_frame.pack(side=TOP)

        # Manual scan buttons
        manual_scan_advance_fraction_5_btn = Button(Manual_scan_btn_frame, text="+5", height=1, state=DISABLED,
                                                    command=manual_scan_advance_frame_fraction_5,
                                                    font=("Arial", FontSize - 1))
        manual_scan_advance_fraction_5_btn.pack(side=LEFT, fill=Y)
        as_tooltips.add(manual_scan_advance_fraction_5_btn, "Advance film by 5 motor steps.")
        manual_scan_advance_fraction_20_btn = Button(Manual_scan_btn_frame, text="+20", height=1, state=DISABLED,
                                                     command=manual_scan_advance_frame_fraction_20,
                                                     font=("Arial", FontSize - 1))
        manual_scan_advance_fraction_20_btn.pack(side=LEFT, fill=Y)
        as_tooltips.add(manual_scan_advance_fraction_20_btn, "Advance film by 20 motor steps.")
        manual_scan_take_snap_btn = Button(Manual_scan_btn_frame, text="Snap", height=1, command=manual_scan_take_snap,
                                           state=DISABLED, font=("Arial", FontSize - 1))
        manual_scan_take_snap_btn.pack(side=RIGHT, fill=Y)
        as_tooltips.add(manual_scan_take_snap_btn, "Take snapshot of frame at current position, then tries to advance "
                                                   "to next frame.")

        # Retreat movie button (slow backward through filmgate)
        RetreatMovie_btn = Button(experimental_miscellaneous_frame, text="Movie Backward", command=retreat_movie,
                                  activebackground='#f0f0f0', relief=RAISED, font=("Arial", FontSize - 1))
        RetreatMovie_btn.grid(row=2, column=0, columnspan=2, padx=x_pad, pady=y_pad)
        as_tooltips.add(RetreatMovie_btn, "Moves the film backwards. BEWARE: Requires manually rotating the source "
                                          "reels in left position in order to avoid film jamming at film gate.")

        # Unlock reels button (to load film, rewind, etc.)
        Free_btn = Button(experimental_miscellaneous_frame, text="Unlock Reels", command=set_free_mode,
                          activebackground='#f0f0f0', relief=RAISED, font=("Arial", FontSize - 1))
        Free_btn.grid(row=3, column=0, columnspan=2, padx=x_pad, pady=y_pad)
        as_tooltips.add(Free_btn, "Used to be a standard button in ALT-Scann8, removed since now motors are always "
                                  "unlocked when not performing any specific operation.")

        # Spinbox to select Preview module
        preview_module_label = tk.Label(experimental_miscellaneous_frame, text='Preview module:',
                                        font=("Arial", FontSize - 1))
        preview_module_label.grid(row=4, column=0, padx=x_pad, pady=y_pad)
        preview_module_value = tk.IntVar(value=1)  # Default value, overriden by configuration
        preview_module_spinbox = DynamicSpinbox(experimental_miscellaneous_frame, command=preview_module_selection,
                                                width=2, textvariable=preview_module_value, from_=1, to=50,
                                                font=("Arial", FontSize - 1))
        preview_module_spinbox.grid(row=4, column=1, padx=x_pad, pady=y_pad, sticky=W)
        preview_module_validation_cmd = preview_module_spinbox.register(preview_module_validation)
        as_tooltips.add(preview_module_spinbox, "Refresh preview, auto exposure and auto WB values only every 'n' "
                                                "frames. Can speed up scanning significantly")
        preview_module_spinbox.configure(validate="key", validatecommand=(preview_module_validation_cmd, '%P'))
        preview_module_spinbox.bind("<FocusOut>", lambda event: preview_module_selection())

    if ExpertMode:
        arrange_widget_state(AE_enabled.get(), [exposure_spinbox])
        arrange_widget_state(not AE_enabled.get(), [auto_exposure_wait_btn,
                                                    AeConstraintMode_label, AeConstraintMode_dropdown,
                                                    AeMeteringMode_label, AeMeteringMode_dropdown,
                                                    AeExposureMode_label, AeExposureMode_dropdown])
        arrange_widget_state(not AWB_enabled.get(), [AwbMode_label, AwbMode_dropdown])

    # Adjust plotter size based on right  frames
    win.update_idletasks()
    plotter_width = integrated_plotter_frame.winfo_width() - 10
    plotter_height = int(plotter_width / 2)
    plotter_canvas.config(width=plotter_width, height=plotter_height)
    # Adjust canvas size based on height of lateral frames
    win.update_idletasks()
    PreviewHeight = max(top_left_area_frame.winfo_height(), top_right_area_frame.winfo_height()) - 20  # Compansate pady
    PreviewWidth = int(PreviewHeight * 4 / 3)
    draw_capture_canvas.config(width=PreviewWidth, height=PreviewHeight)
    # Adjust holes size/position
    FilmHoleHeightTop = int(PreviewHeight / 5.9)
    FilmHoleHeightBottom = int(PreviewHeight / 3.7)
    # Adjust main window size
    # Prevent window resize
    # Get screen size - maxsize gives the usable screen size
    main_container.update_idletasks()
    app_width = min(main_container.winfo_reqwidth(), screen_width - 150)
    app_height = min(main_container.winfo_reqheight(), screen_height - 150)
    win.minsize(app_width, app_height)
    win.maxsize(app_width, app_height)
    win.geometry(f'{app_width}x{app_height - 20}')  # setting the size of the window


def get_controller_version():
    if Controller_Id == 0:
        logging.debug("Requesting controller version")
        send_arduino_command(CMD_VERSION_ID)


def reset_controller():
    logging.debug("Resetting controller")
    send_arduino_command(CMD_RESET_CONTROLLER)
    time.sleep(0.5)


def main(argv):
    global SimulatedRun
    global ExpertMode, ExperimentalMode, PlotterMode
    global LogLevel, LoggingMode
    global ALT_scann_init_done
    global CameraDisabled, DisableThreads
    global FontSize, add_vertical_scrollbar
    global keep_control_widgets_enabled

    go_disable_tooptips = False

    opts, args = getopt.getopt(argv, "sexl:phntwf:b")

    for opt, arg in opts:
        if opt == '-s':
            SimulatedRun = True
        elif opt == '-e':
            ExpertMode = not ExpertMode
        elif opt == '-x':
            ExperimentalMode = not ExperimentalMode
        elif opt == '-d':
            CameraDisabled = True
        elif opt == '-l':
            LoggingMode = arg
        elif opt == '-f':
            FontSize = int(arg)
        elif opt == '-b':
            add_vertical_scrollbar = True
        elif opt == '-n':
            go_disable_tooptips = True
        elif opt == '-t':
            DisableThreads = True
        elif opt == '-p':
            PlotterMode = not PlotterMode
        elif opt == '-w':
            keep_control_widgets_enabled = not keep_control_widgets_enabled
        elif opt == '-h':
            print("ALT-Scann 8 Command line parameters")
            print("  -s             Start Simulated session")
            print("  -e             Activate expert mode")
            print("  -x             Activate experimental mode")
            print("  -p             Activate integrated plotter")
            print("  -d             Disable camera (for development purposes)")
            print("  -n             Disable Tooltips")
            print("  -t             Disable multi-threading")
            print("  -f             Set default font size for UI (11 by default)")
            print("  -b             Add scrollbars to UI (in case it does not fit)")
            print("  -w             Keep control widgets enabled while scanning")
            print("  -l <log mode>  Set log level (standard Python values (DEBUG, INFO, WARNING, ERROR)")
            exit()

    LogLevel = getattr(logging, LoggingMode.upper(), None)
    if not isinstance(LogLevel, int):
        raise ValueError('Invalid log level: %s' % LogLevel)

    ALT_scann_init_done = False

    load_persisted_data_from_disk()  # Read json file in memory, to be processed by 'load_session_data'

    tscann8_init()

    if go_disable_tooptips:
        as_tooltips.disable()

    load_config_data()
    load_session_data()

    if SimulatedRun:
        logging.debug("Starting in simulated mode.")
    if ExpertMode:
        logging.debug("Toggle expert mode.")
    if ExperimentalMode:
        logging.debug("Toggle experimental mode.")
    if CameraDisabled:
        logging.debug("Camera disabled.")
    if FontSize != 0:
        logging.debug(f"Font size = {FontSize}")
    if DisableThreads:
        logging.debug("Threads disabled.")
    if PlotterMode:
        logging.debug("Toggle ploter mode.")

    if not SimulatedRun:
        arduino_listen_loop()

    ALT_scann_init_done = True

    onesec_periodic_checks()

    # Main Loop
    win.mainloop()  # running3 the loop that works as a trigger

    if not SimulatedRun and not CameraDisabled:
        camera.close()


if __name__ == '__main__':
    main(sys.argv[1:])
