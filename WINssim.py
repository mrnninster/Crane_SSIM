# Application Imports
from skimage.metrics import structural_similarity as compare_ssim
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tqdm import tqdm
import matplotlib.pyplot as plt
import PySimpleGUI as sg
import datetime as dt
import pandas as pd
import numpy as np
import threading
import logging
import sqlite3
import copy
import time
import csv
import cv2
import gi
import re
import os
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk

###############
# Logger
###############

# ------- Configuring Logging File -------- #

# Logger For Log File
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Log File Logging Format
formatter = logging.Formatter("%(asctime)s:%(levelname)s::%(message)s")

# Log File Handler
Log_File_Handler = logging.FileHandler("WINSSIM.log")
Log_File_Handler.setLevel(logging.DEBUG)
Log_File_Handler.setFormatter(formatter)

# Stream Handlers
Stream_Handler = logging.StreamHandler()

# Adding The Handlers
logger.addHandler(Log_File_Handler)
logger.addHandler(Stream_Handler)

logger.debug("")
logger.debug("="*100)

logger.info("Starting App")

logger.info("Imports Complete")


########################
# Monitor Control
########################


# ------ Monitor Count and Details Using Gdk------ #
display = Gdk.Display.get_default()
screen = display.get_default_screen()
window = screen.get_active_window()

# collect data about monitors
number_of_monitors = display.get_n_monitors()
logger.debug(f"Detected {number_of_monitors} number of monitors")
monitor_dimensions = dict()

for index in range(number_of_monitors):
    monitor = display.get_monitor(index)
    geometry = monitor.get_geometry()

    # Primary Monitor Detection
    if monitor.is_primary():
        logger.debug(f"Monitor {index + 1} = {geometry.width}x{geometry.height} (primary)")
    else:
        logger.debug(f"Monitor {index + 1} = {geometry.width}x{geometry.height}")

    # Append To Monitor Dict
    monitor_dimensions[f"Monitor_{index + 1}_Width"] = geometry.width
    monitor_dimensions[f"Monitor_{index + 1}_Height"] = geometry.height


############################
# DataBase Schema
############################

# ------- SQLITE DataBase Creation -------- #

# Database Connection Variable
conn = sqlite3.connect("WinSsim.db")

# Sqlite Cursor
c = conn.cursor()

# Define Table
try:
    # Create New Mirror Standard Table
    c.execute(""" CREATE TABLE nmsctrl (
        Crop_Status string,
        Sync_Status string,
        Crop_X1 integer,
        Crop_X2 integer,
        Crop_Y1 integer,
        Crop_Y2 integer,
        Sync_X1 integer,
        Sync_X2 integer,
        Sync_Y1 integer,
        Sync_Y2 integer,
        Multi_Sync string,
        Multi_Crop string,
        Mode string,
        Bbox_Count integer,
        Bbox_Data string


    )""")

    # Commit Table
    conn.commit()

    # Create Camera Control Table
    c.execute(""" CREATE TABLE camctrl (
        Camera_1 boolean,
        Camera_2 boolean,
        Camera_3 boolean,
        Focus_Val integer
    )""")

    # Commit Table
    conn.commit()


    # Create Other Setting Table
    c.execute(""" CREATE TABLE othsetctrl (
        Timer integer,
        Log_Level string,
        Bbox_Line_Width integer,
        Bbox_Line_Colour string,
        Thumbnails_Width integer,
        Thumbnails_Height integer,
        NMS_Master_Pattern_Folder_Path string,
        NMS_Master_Thumbnails_Folder_Path string,
        Result_Destination string,
        Origin_Pattern_Folder string
    )""")

    # Commit Table
    conn.commit()

except Exception as e:
    # Pass if table already exist
    pass
    logger.info(f"skipping DataBase Creation: {e}")

else:
    # Create Default Camera Control Values
    c.execute(
        "INSERT INTO camctrl VALUES (True,False,False,35)")

    # Commit Insert Tranx
    conn.commit()
    logger.debug("Created Default Camera Control Database")

    # Create Default NMS Control Values
    c.execute(
        f"INSERT INTO nmsctrl VALUES ('Disabled','Enabled',10,100,10,100,10,100,10,100,'Enabled','Disabled','single',1,'None')")

    # Commit Insert Tranx
    conn.commit()
    logger.debug("Created Default NMS Control Database")

    # Create Default Other Setting Values
    c.execute("INSERT INTO othsetctrl VALUES (10,'INFO',2,'RED',150,150,'Mirror_Standard/MirrorStandards','Mirror_Standard/Thumbnails','Mirror_Standard/Results','Mirror_Standard/Origin_Folder')")

    # Commit Insert Tranx
    conn.commit()
    logger.debug("Created Other Setting Table")

    # DB Successfully Created
    logger.info("Database Successfully created")


"""
Connects to database and pulls data from specified table
"""
def database(table):
    # Select Current Values of Parameters
    c.execute(f"SELECT * FROM {table} WHERE rowid=1")

    # Commit Fech Tranx
    db_data = c.fetchone()
    conn.commit()

    return db_data


# -------- Window U.I Development Functions -------- #

# Menu Definition 
menu_def = [['Settings', ['Mirror Standard Settings','View Origin Images','Collect Batch Data','Set Up Camera','Other Settings','Help']]]

# Section Headers
New_Sample_Section = [
    [sg.Text("-"*40+"\nNEW SAMPLE SECTION", size=(30, 2), text_color="White", font=("Courier 20",30), justification="center")]
]

###############################
# Home Window Widgets 
###############################

# Home_Date
Date = [
    [sg.Text("Date", size=(19, 1), text_color="black", background_color="white", font="Courier 10", justification="center")],
    [sg.Text(dt.datetime.date(dt.datetime.now()), size=(12, 1), text_color="black", background_color="white", font=("Courier 10", 17), justification="center", key="Current_Date")]
    ]

# Home_Sample Name
Sample_Name = [
    [sg.Text("Sample Name", size=(100, 1), text_color="black", background_color="white", font="Courier 10", justification="center")],
    [sg.Text("Current Sample Name", size=(30, 1), text_color="black", background_color="white", font=("Courier 10", 17), justification="center", key="Sample_Key")]
    ]

# Home_Control Buttons
Control_Buttons = [

    # App Control
    [sg.Button("START", button_color=('white', 'green'), enable_events=True,  font=('Courier 20',20),size=(16,1)),  
    sg.Button("CLOSE", button_color=('white', 'red'), enable_events=True,  font=('Courier 20',20),size=(16,1))]
    ]

# Home_Previous Data Button
Previous_Analysis_Button = [
    [sg.Button("VIEW PREVIOUS ANALYSIS", button_color=('white', 'brown'), enable_events=True, font=("Courier 20",25), size=(50,1), key="-Previous_Analysis-")]
]


############################
# Other Setting Variables
############################

# Other Setting Database Connection
othset_data = database("othsetctrl")

# Count_Down Timer
Count_Down_Timer = othset_data[0]

# Set Log_Level
App_Log_Level = othset_data[1]

# Nms Bbox Display Variables
Bbox_Line_Width = othset_data[2]

# Bbox_Line_Width_DropDowm
Bbox_Width_List = ["One(1) Pixel","Two(2) Pixels","Three(3) Pixels"]

# Bbox_Line_Color
Bbox_Color_in_DB = othset_data[3]

Bbox_Color_Dict = {
    "WHITE":(255,255,255),
    "RED":(0,0,255),
    "BLUE":(255,0,0),
    "GREEN":(0,255,0),
    "BLACK":(0,0,0)
    }

Bbox_Line_Color = Bbox_Color_Dict[Bbox_Color_in_DB.upper()]

# Thumbnail_Dimensions
Thumbnail_Width = othset_data[4]
Thumbnail_Height = othset_data[5]

# NMS Master Folder
NMS_Master_Pattern_Folder = f"{othset_data[6]}"

# Make Master Folder if Not Exist
os.makedirs(NMS_Master_Pattern_Folder,exist_ok=True)

# NMS Thumbnails Folder
NMS_Master_Thumbnails_Folder = f"{othset_data[7]}"

# Make Thumbnails Folder if Not Exist
os.makedirs(NMS_Master_Thumbnails_Folder, exist_ok=True)

# Analysis Results Folder
Analysis_Results_Folder = f"{othset_data[8]}"

# Make Results Folder if Not Exist
os.makedirs(Analysis_Results_Folder, exist_ok=True)

# Pattern Origin Folder
Origin_Folder = f"{othset_data[9]}"

# Make Origin Folder if Not Exist
os.makedirs(Origin_Folder, exist_ok=True)


##############################
# ACTIVE SESSION VARIABLES
##############################
"""
This variable is used to keep track of the threads
created by the coundown timer, ensuring that only one
thread is running at any giving time
"""
All_Threads = list()

# Number of Patterns To Loop Over
Pattern_Count = len(os.listdir(NMS_Master_Pattern_Folder))

# List Of Properly Named Pattern Files
List_Of_Proper_Pattern_Names = [x for x in os.listdir(NMS_Master_Pattern_Folder) if x.endswith("Pattern.png")]

# Default Display Pattern
Default_Pattern = f"{NMS_Master_Pattern_Folder}/{os.listdir(NMS_Master_Thumbnails_Folder)[0]}"
Default_Thumbnail = f"{NMS_Master_Thumbnails_Folder}/{os.listdir(NMS_Master_Thumbnails_Folder)[0]}"

# Timer Thread Exit Event
Exit_Thread = threading.Event()


######################
# NMS DB Data
######################

# NMS Control Database Connection
nms_data = database("nmsctrl")

# NMS Crop Status
Crop_Status = nms_data[0]

# NMS Bbox Status
Sync_Status = nms_data[1]


# Functions
"""
Pattern Files Renaming Function
-> Creates Properly Named Patten Files
-> Removes Improperly Named Pattern Files

Master_Pattern_Folder: Path To Folder Containing Patterns
"""
def Rename_Patterns(Master_Pattern_Folder = NMS_Master_Pattern_Folder):

    # Identify Improperly Named Patterns
    To_Rename = [x for x in os.listdir(Master_Pattern_Folder) if x not in List_Of_Proper_Pattern_Names]

    # Creating Thumbnails
    if To_Rename != []:
        logger.debug("Renaming Pattern Files")

        Pattern_Number = len(List_Of_Proper_Pattern_Names)

        for img in tqdm(To_Rename, desc = "Creating Renamed Files"):
            Current_img = cv2.imread(f"{Master_Pattern_Folder}/{img}")
            Pattern_Number = int(Pattern_Number)
            Pattern_Number += 1
            if len(str(Pattern_Number)) < 2:
                Pattern_Number = f"0{Pattern_Number}"
            cv2.imwrite(f"{Master_Pattern_Folder}/{Pattern_Number}_Pattern.png",Current_img)
        
        logger.debug("Renamed All Pattern Files")
        
        logger.debug("Cleaning Up Pattern Folder")
        
        for File in tqdm(To_Rename, desc = "Removing Improperly Named Files"):
            os.remove(f"{Master_Pattern_Folder}/{File}")
        
        logger.debug("Pattern Folder Cleaned")

# Rename Pattern Files
if Pattern_Count != len(List_Of_Proper_Pattern_Names):
    Rename_Patterns()


"""
Thumbnail Generator Section
-> Creates Thumbnails For Master Images
-> Adds Thumbnails For New Images
-> Removes Unused Thumbnails

NMS_Master_Pattern_Folder: Path to the folder containing all the pattern images]
Thumbnail_Image_Folder: Path to the folder containing all the thumbnails
Thumbnail_Width: The specified width of the thumbnail
Thumbnail_Height: The specified height of the thumbnail
"""
def Thumbnails(Master_Image_Folder=NMS_Master_Pattern_Folder, Thumbnails_Image_Folder=NMS_Master_Thumbnails_Folder, Thumnbail_Width=Thumbnail_Width, Thumbnail_Height=Thumbnail_Height):
    
    #Logging
    logger.debug("Checking For Thumbnails Update") 

    # Identify Files Without Thumbnails
    Img_Files = [x for x in os.listdir(Master_Image_Folder) if x not in os.listdir(Thumbnails_Image_Folder)]

    # Creating Thumbnails
    if Img_Files != []:
        logger.debug("Updating Thumbnails")

        for img in tqdm(Img_Files, desc = "Creating Thumbnails"):
            Current_img = cv2.imread(f"{Master_Image_Folder}/{img}")
            resized_img = cv2.resize(Current_img, (Thumbnail_Width, Thumbnail_Height), interpolation=cv2.INTER_AREA)
            cv2.imwrite(f"{Thumbnails_Image_Folder}/{img}",resized_img)
        
        logger.debug("Update Concluded")

    logger.debug("Checking For Unused Thumbnails")

    # Identifying Deleted Files
    Del_Files = [x for x in os.listdir(Thumbnails_Image_Folder) if x not in os.listdir(Master_Image_Folder)]

    # Removing Thumbnails Of Deleted Stamdard Images
    if Del_Files != []:
        logger.debug("Clearing Unused Thumbnails")

        for img in tqdm(Del_Files, desc = "Removing Unused Thumbnails"):
            os.remove(f"{Thumbnails_Image_Folder}/{img}")
        
        logger.debug("Thumbails Cleared")

    # Resizing Thumbnails
    Pick_File = os.listdir(Thumbnails_Image_Folder)[0]
    Read_Image = cv2.imread(f"{Thumbnails_Image_Folder}/{Pick_File}")
    
    if Read_Image.shape[0] != Thumbnail_Width:
        logger.debug("Resizing Thumbnails")
        All_Thumbnails = [x for x in os.listdir(Thumbnails_Image_Folder)]

        for Thumbnail in All_Thumbnails:
            Current_img = cv2.imread(f"{Master_Image_Folder}/{Thumbnail}")
            resized_img = cv2.resize(Current_img, (Thumbnail_Width, Thumbnail_Height), interpolation=cv2.INTER_AREA)
            cv2.imwrite(f"{Thumbnails_Image_Folder}/{Thumbnail}",resized_img)
        
        logger.debug("Resize Complete")

# Generate Thumbnails
Thumbnails()

"""
Bounding Box Coordinate UI Generator For PySimpleGui
-> Create input UI in the pattern (X,Y)

label: The label of the generated widget
begin_x: The bbox starting point in the x axis
begin_y: The bbox starting point in the y axis
key1: PySimpleGUI key for begin_x
key2: PySimpleGUI key for begin_y 
"""
def create_coords_elements(label, begin_x, begin_y, key1, key2):
    return [
        [sg.Text(label, font=("Courier 10",12))],
        [
        sg.Input(begin_x, size=(8, 1), key=key1, enable_events=True, background_color = ("gray"), disabled=True),
        sg.Input(begin_y, size=(8, 1), key=key2, enable_events=True, background_color = ("gray"), disabled=True)]
    ]

"""
Countdown Timer Function
-> Manual Mode
-> Automated Mode
-> Runs iteratively through defined Count_Down_Timer value
-> Creates Event To Update Timer Display
-> Activate Analysis when timer hits 1 secs

window: PySimpleGUI window where the function is called
ct_time: The amount of time to count down in secs
manual: Activates the manual mode by setting the delay time to 1 secs
auto: Automated mode for automatically counting down from the specified time
"""

# Timer Function
def countdown(window, ct_time, manual=False, auto=True):
    if manual:
        ct_time = 1

    while ct_time:
        # Break OUT Of Loop If Exit Codition Is Met
        if Exit_Thread.is_set():
            break
        
        # Keep On Running If It Isn't
        else:
            mins, secs = divmod(ct_time, 60)
            Current_Time = '{:02d}:{:02d}'.format(mins, secs)

            # Check To Prevent Errors On Window Close
            try:
                window.write_event_value('-THREAD_TIMER-', Current_Time)
            except:
                break

            time.sleep(1)
            ct_time -= 1
            if str(Current_Time) == "00:01":
                try:
                    # Write Even To Capture Image Update Operations Window
                    window.write_event_value('-SSIM_ACTIVATE-', Current_Time)
                except Exception as e:
                    logger.exception(str(e))


""" 
Home Window Section
"""
def Home_Win():
    
    # Window Location
    Home_Width = 550
    Home_Height = 290
    Home_Pos_Width = (monitor_dimensions["Monitor_1_Width"] - Home_Width)/2
    Home_Pos_Height  = (monitor_dimensions["Monitor_1_Height"] - Home_Height)/2

    # Using Earlier Defined Home Widgets
    Home_layout = [

            # Menu Definition 
            [sg.Menu(menu_def)],

            # Pevious Analysis
            [Previous_Analysis_Button],


            # New Sample Section
            [New_Sample_Section],

            # Product ID Input
            [
            sg.Text('Set Collection Name:', size=(21, 1), text_color='black', background_color='white', font='Courier 10', justification="center"), 
            sg.InputText(size=(50, 1), key="Sample_ID")
            ],
            
            # Close App
            [Control_Buttons]]

    # Create Window
    Win = sg.Window('Home Window', Home_layout, location=(Home_Pos_Width, Home_Pos_Height), size=(Home_Width,Home_Height), keep_on_top=True, finalize=True)
    return Win


"""
New Mirror Standard Creation Section
-> Displays both screen on single monitor when just 1 is detected
-> Displays on 2 monitors when 2 or more monitors are detected
-> Displays live feed in one screen and patters in another screen
-> Activation and manipulation of boundary box for image cropping
-> Enable or disabled boundary box align
-> Abilty to take sample picture
-> Ability to carry out SSIM on sample picture
-> Replace Mirror Standard Button
-> Save Settings Button
"""
# Camera View Display
def NMS_Cam_View():

    # Window Location
    NMS_Cam_View_Width = monitor_dimensions["Monitor_1_Width"] -100
    NMS_Cam_View_Height = (monitor_dimensions["Monitor_1_Height"]-100)
    NMS_Cam_Display_Width = (NMS_Cam_View_Width - 250)
    NMS_Cam_Display_Height = (NMS_Cam_View_Height - 30)
    NMS_Cam_View_Screen_Position_Width = (monitor_dimensions["Monitor_1_Width"] - NMS_Cam_View_Width)/2
    NMS_Cam_View_Screen_Position_Height  = (monitor_dimensions["Monitor_1_Height"] - NMS_Cam_View_Height)/5

    # DataBase Data Fetch
    nms_data = database("nmsctrl")

    # New Mirror Standard Widgets
    NMS_Cam_Setting_Header = [sg.Text("CONTROLS", font=("Courier 20", 20))]

    # BBOX Displayed Count
    Bbox_Count_Header = [sg.Text("NUMBER OF BBOX", font=("Courier 12", 12))]
    No_Of_Bbox = [sg.InputText(nms_data[13], enable_events=True, font=("Courier 10",10), size=(19,1), key="-Bbox_Count-")]

    # NMS_Buttons
    NMS_Picture_Button = [sg.Button("TAKE PICTURE", button_color=("white","green"), enable_events=True, font=("Courier 10",10), size=(16,1))]

    NMS_Stream_Button = [sg.Button("START STREAM", button_color=("white","brown"), enable_events=True, font=("Courier 10",10), size=(16,1))]

    NMS_Activate_Crop_Button = [sg.Button("ENABLE CROP", button_color=("white","green"), enable_events=True, font=("Courier 10",10), size=(16,1), key=("-Enable Crop-"), disabled=False)]

    NMS_Deactivate_Crop_Button =[sg.Button("DISABLE CROP", button_color=("white","brown"), enable_events=True, font=("Courier 10",10), size=(16,1), key=("-Disable Crop-"), disabled=True)]

    NMS_Update_Bbox_Count = [sg.Button("UPDATE", enable_events=True, font=("Courier 10",10), size=(16,1), key=("-Update_Crop-"))]

    NMS_Activate_Sync_Button = [sg.Button("ENABLE SYNC", button_color=("white","green"), enable_events=True, font=("Courier 10",10), size=(16,1), key=("-Enable Sync-"), disabled=True)]

    NMS_Deactivate_Sync_Button =[sg.Button("DISABLE SYNC", button_color=("white","brown"), enable_events=True, font=("Courier 10",10), size=(16,1), key=("-Disable Sync-"), disabled=False)]

    NMS_Test_SSIM_Button = [sg.Button("SSIM TEST", button_color=("white","brown"), enable_events=True, font=("Courier 10",10), size=(16,1), key=("-Ssim Test-"))]

    Sample_SSIM, Sample_SSIM_Result = [sg.Text("SAMPLE RESULT", size=(16, 1), text_color="black", background_color="white", font=("Courier 10", 10), justification="center")],[sg.Text("0000", size=(10, 1), text_color="black", background_color="white", font=("Courier 10", 17), justification="center", key="S_ssim")]

    NMS_Save_Button = [sg.Button("SAVE", button_color=('white', 'green'), enable_events=True,  font=('Courier 10',10), size=(16,1))]

    NMS_Pattern_Buttons = [sg.Button("ADD", font=('Courier 10',8), button_color=('white','green'), size=(5,1), key=("-Add-")), sg.Button("REPLACE", font=('Courier 10',8), size=(8,1), key=("-Replace-")),sg.Button("REMOVE", font=('Courier 10',8), button_color=('white', 'red'), size=(8,1), key=("-Remove-"))]

    Control_Col = [
                # Setting Header
                NMS_Cam_Setting_Header,
                
                # Take Picture Button
                NMS_Picture_Button,
                NMS_Stream_Button,
                [sg.Text('_'*20)],

                # No Of Bbox Displayed Control
                Bbox_Count_Header,
                No_Of_Bbox,
                NMS_Update_Bbox_Count,
                [sg.Text('_'*20)],

                # Image Crop Utility
                
                NMS_Activate_Crop_Button,
                NMS_Deactivate_Crop_Button,
                [sg.Text('_'*20)],

                # X-Coordinates
                *create_coords_elements("BEGIN CO-ORDS",f"{nms_data[2]}", f"{nms_data[4]}", "-CROP_BEGIN_X-", "-CROP_BEGIN_Y-"),
                
                # Y-Coordinates
                *create_coords_elements("END CO-ORDS",f"{nms_data[3]}", f"{nms_data[5]}", "-CROP_END_X-", "-CROP_END_Y-"),
                [sg.Text('_'*20, key="-Img_Coord_Seperator-")],

                # Image Bbox Utility
                NMS_Activate_Sync_Button,
                NMS_Deactivate_Sync_Button,
                [sg.Text('_'*20, key="-Sync_Button_Seperator-")],

                # X-Coordinates
                *create_coords_elements("BEGIN CO-ORDS",f"{nms_data[6]}", f"{nms_data[8]}", "-SYNC_BEGIN_X-", "-SYNC_BEGIN_Y-"),
                
                # Y-Coordinates
                *create_coords_elements("END CO-ORDS",f"{nms_data[7]}", f"{nms_data[9]}", "-SYNC_END_X-", "-SYNC_END_Y-"),
                [sg.Text('_'*20, key="-Pattern_Coord_Seperator-")],
                
                # Image SSIM Test Utility
                NMS_Test_SSIM_Button,
                Sample_SSIM,
                Sample_SSIM_Result,
                [sg.Text('_'*20)],

                # Image Save Utility
                NMS_Save_Button,

                # Pattern Buttons
                NMS_Pattern_Buttons]

    # Live Stream Section From The Camera
    Stream_Col = [[sg.Image(filename="", key="camera")]]

    #  Layout Section
    NMS_Cam_View_Layout  = [[sg.Column(Control_Col, element_justification='c', scrollable=True, vertical_scroll_only=True, expand_y=True), sg.VSeperator(),sg.Column(Stream_Col, element_justification='c')]]

    # Create Window
    MS_Win = sg.Window('Camera View Window', NMS_Cam_View_Layout, location=(NMS_Cam_View_Screen_Position_Width, NMS_Cam_View_Screen_Position_Height), size=(NMS_Cam_View_Width,NMS_Cam_View_Height), keep_on_top=True, finalize=True)
    return MS_Win, NMS_Cam_Display_Width, NMS_Cam_Display_Height


# NMS CAM BBOX CONTROL WINDOW
def NMS_Bbox_Control_Win(Count = 2):

    # Window Location
    NMS_Bbox_Control_View_Width = int(350)
    NMS_Bbox_Control_View_Height = (monitor_dimensions["Monitor_1_Height"]-300)
    NMS_Bbox_Control_Display_Width = (NMS_Bbox_Control_View_Width - 250)
    NMS_Bbox_Control_Display_Height = (NMS_Bbox_Control_View_Height - 30)
    NMS_Bbox_Control_View_Screen_Position_Width = 50
    NMS_Bbox_Control_View_Screen_Position_Height  = (monitor_dimensions["Monitor_1_Height"] - NMS_Bbox_Control_View_Height)/5

    NMS_Deactivate_Sync_Button =[sg.Button("DISABLE SYNC", button_color=("white","brown"), enable_events=True, font=("Courier 10",10), size=(16,1), key=("-Disable Sync-"), disabled=False)]

    # Window Variables
    Image_Widget_Id = 0

    # Position Of The Bbox
    multiplier = 10

    Multi_Bbox_Control = list()

    # Image Bbox Utility
    nmsctrl_data = database("nmsctrl")
    if(nmsctrl_data[10] == "Disabled"):    
        Multi_Bbox_Control.append([sg.Button(f"ENABLE MULTI-SYNC", button_color=("white","green"), enable_events=True, font=("Courier 10",10), size=(18,1), key=(f"-Enable_Multi_Sync-"), disabled=False)])
        Multi_Bbox_Control.append([sg.Button(f"DISABLE MULTI-SYNC", button_color=("white","brown"), enable_events=True, font=("Courier 10",10), size=(18,1), key=(f"-Disable_Multi_Sync-"), disabled=True)])
    
    elif(nmsctrl_data[10] == "Enabled"):
        Multi_Bbox_Control.append([sg.Button(f"ENABLE MULTI-SYNC", button_color=("white","green"), enable_events=True, font=("Courier 10",10), size=(18,1), key=(f"-Enable_Multi_Sync-"), disabled=True)])
        Multi_Bbox_Control.append([sg.Button(f"DISABLE MULTI-SYNC", button_color=("white","brown"), enable_events=True, font=("Courier 10",10), size=(18,1), key=(f"-Disable_Multi_Sync-"), disabled=False)])

    Multi_Bbox_Control.append([sg.Text('_'*20)])

    # Bbox Displayed On Image
    for i in range(Count):
        Image_Widget_Id += 1

        # Header
        Multi_Bbox_Control.append([sg.Text(f"CONTROLS FOR BBOX {Image_Widget_Id}", font=("Courier 18", 18))])
        
        Bbox_Value = eval(nmsctrl_data[14])

        try:
            # X-Coordinates
            [Multi_Bbox_Control.append(x) for x in create_coords_elements(f"IMAGE BEGIN CO-ORDS BBOX","{}".format(Bbox_Value[f"CB_X_Bbox_{Image_Widget_Id}"]), "{}".format(Bbox_Value[f"CB_Y_Bbox_{Image_Widget_Id}"]), f"-CROP_BEGIN_X_{Image_Widget_Id}-", f"-CROP_BEGIN_Y_{Image_Widget_Id}-")]
            
            # Y-Coordinates
            [Multi_Bbox_Control.append(x) for x in create_coords_elements(f"IMAGE END CO-ORDS BBOX ","{}".format(Bbox_Value[f"CE_X_Bbox_{Image_Widget_Id}"]), "{}".format(Bbox_Value[f"CE_Y_Bbox_{Image_Widget_Id}"]), f"-CROP_END_X_{Image_Widget_Id}-", f"-CROP_END_Y_{Image_Widget_Id}-")]
            Multi_Bbox_Control.append([sg.Text('_'*20)])

            # X-Coordinates
            [Multi_Bbox_Control.append(x) for x in create_coords_elements(f"PATTERN BEGIN CO-ORDS BBOX","{}".format(Bbox_Value[f"SB_X_Bbox_{Image_Widget_Id}"]), "{}".format(Bbox_Value[f"SB_Y_Bbox_{Image_Widget_Id}"]), f"-SYNC_BEGIN_X_{Image_Widget_Id}-", f"-SYNC_BEGIN_Y_{Image_Widget_Id}-")]
            
            # Y-Coordinates
            [Multi_Bbox_Control.append(x) for x in create_coords_elements(f"PATTERN END CO-ORDS BBOX","{}".format(Bbox_Value[f"SE_X_Bbox_{Image_Widget_Id}"]), "{}".format(Bbox_Value[f"SE_Y_Bbox_{Image_Widget_Id}"]), f"-SYNC_END_X_{Image_Widget_Id}-", f"-SYNC_END_Y_{Image_Widget_Id}-")]
            Multi_Bbox_Control.append([sg.Text('_'*20)])
        
        except:
            # X-Coordinates
            Start_Positions = multiplier * Image_Widget_Id
            [Multi_Bbox_Control.append(x) for x in create_coords_elements(f"IMAGE BEGIN CO-ORDS BBOX",f"{Start_Positions}", f"{Start_Positions}", f"-CROP_BEGIN_X_{Image_Widget_Id}-", f"-CROP_BEGIN_Y_{Image_Widget_Id}-")]
            
            # # Y-Coordinates
            [Multi_Bbox_Control.append(x) for x in create_coords_elements(f"IMAGE END CO-ORDS BBOX ",f"{Start_Positions + 100}", f"{Start_Positions + 100}", f"-CROP_END_X_{Image_Widget_Id}-", f"-CROP_END_Y_{Image_Widget_Id}-")]
            Multi_Bbox_Control.append([sg.Text('_'*20)])

            # # X-Coordinates
            [Multi_Bbox_Control.append(x) for x in create_coords_elements(f"PATTERN BEGIN CO-ORDS BBOX",f"{Start_Positions}", f"{Start_Positions}", f"-SYNC_BEGIN_X_{Image_Widget_Id}-", f"-SYNC_BEGIN_Y_{Image_Widget_Id}-")]
            
            # # Y-Coordinates
            [Multi_Bbox_Control.append(x) for x in create_coords_elements(f"PATTERN END CO-ORDS BBOX",f"{Start_Positions + 100}", f"{Start_Positions + 100}", f"-SYNC_END_X_{Image_Widget_Id}-", f"-SYNC_END_Y_{Image_Widget_Id}-")]
            Multi_Bbox_Control.append([sg.Text('_'*20)])

    
        # Image SSIM Test Utility
        Multi_Bbox_Control.append([sg.Button(f"SSIM TEST {Image_Widget_Id}", button_color=("white","brown"), enable_events=True, font=("Courier 10",10), size=(16,1), key=(f"-Ssim_Test_{Image_Widget_Id}-"))])
        Multi_Bbox_Control.append([sg.Text(f"SAMPLE RESULT {Image_Widget_Id}", size=(16, 1), text_color="black", background_color="white", font=("Courier 10", 10), justification="center")])
        Multi_Bbox_Control.append([sg.Text("0000", size=(10, 1), text_color="black", background_color="white", font=("Courier 10", 17), justification="center", key=f"S_ssim_{Image_Widget_Id}")])
        Multi_Bbox_Control.append([sg.Text('')])

    # Image Bbox Utility
    Multi_Bbox_Control.append([sg.Text('_'*20)])
    Multi_Bbox_Control.append([sg.Button(f"SAVE", button_color=("white","green"), enable_events=True, font=("Courier 10",10), size=(16,1), key=(f"-SAVE_Multi_Crop-"))])

    #  Layout Section
    NMS_Bbox_Control_View_Layout  = [[sg.Column(Multi_Bbox_Control, element_justification='c', scrollable=True, vertical_scroll_only=True, expand_y=True)]]

    # Create Window
    NMS_Bbox_Control_Win = sg.Window('Mutil Bbox Control Window', NMS_Bbox_Control_View_Layout, location=(NMS_Bbox_Control_View_Screen_Position_Width, NMS_Bbox_Control_View_Screen_Position_Height), size=(NMS_Bbox_Control_View_Width,NMS_Bbox_Control_View_Height), keep_on_top=True, finalize=True)
    return NMS_Bbox_Control_Win, NMS_Bbox_Control_Display_Width, NMS_Bbox_Control_Display_Height

# Human Sort
def atoi(text):
    return int(text) if text.isdigit() else text

def natural_keys(text):
    return [ atoi(c) for c in re.split(r'(\d+)', text) ]

"""
Pattern Display Section
-> Displays A list of Patterns To Work With
-> Each Pattern is Selectable
-> Each Selected Pattern is Displayed on The Screen

Helper Functions: "A Test Of Integer(atoi)" and "nutural_keys" are helpful functions
for the NMS_Master_Window to order the display of the thumbnails

NMS_Master_Thumbnails_Folder_Path: The Path To The Thumbnails Folder
Default_Pattern: The First Pattern Image Displayed When The Window Is Launched
"""
# Pattern Control Section
def NMS_Pattern_View(NMS_Master_Thumbnails_Folder_Path = NMS_Master_Thumbnails_Folder, Default_Pattern = Default_Pattern, Monitor_Count = number_of_monitors):

    if Monitor_Count < 2:

        # Window Metrics
        NMS_Pattern_View_Width = monitor_dimensions["Monitor_1_Width"] - 100
        NMS_Pattern_View_Height = (monitor_dimensions["Monitor_1_Height"] - 100)
        NMS_Pattern_Display_Width = (NMS_Pattern_View_Width - 250)
        NMS_Pattern_Display_Height = (NMS_Pattern_View_Height - 30)
        NMS_Pattern_View_Screen_Position_Width = (monitor_dimensions["Monitor_1_Width"] - NMS_Pattern_View_Width)/2
        NMS_Pattern_View_Screen_Position_Height  = (monitor_dimensions["Monitor_1_Height"] - NMS_Pattern_View_Height)/5
    
    else:

        # Window Metrics
        NMS_Pattern_View_Width = (monitor_dimensions["Monitor_2_Width"] - 100)
        NMS_Pattern_View_Height = (monitor_dimensions["Monitor_2_Height"] - 100)
        NMS_Pattern_Display_Width = (NMS_Pattern_View_Width - 250)
        NMS_Pattern_Display_Height = (NMS_Pattern_View_Height - 30)
        NMS_Pattern_View_Screen_Position_Width = monitor_dimensions["Monitor_1_Width"] + ((monitor_dimensions["Monitor_2_Width"] - NMS_Pattern_View_Width)/2)
        NMS_Pattern_View_Screen_Position_Height  = (monitor_dimensions["Monitor_2_Height"] - NMS_Pattern_View_Height)/5


    # NMS PATTERN WINDOW WIDGETS
    Thumbnail_Folder_Content = os.listdir(NMS_Master_Thumbnails_Folder_Path)
    Thumbnail_Folder_Content.sort(key=natural_keys)

    NMS_Master_Thumbnails_List = [[sg.ReadFormButton(f"{image}", image_filename=f"{NMS_Master_Thumbnails_Folder_Path}/{image}", image_size=(150, 150), border_width=0)] for image in Thumbnail_Folder_Content]

    # Pattern Display Section
    Display_Image = cv2.imread(f"{Default_Pattern}")
    Resized_Display_Image = cv2.resize(Display_Image, (NMS_Pattern_Display_Width, NMS_Pattern_Display_Height),interpolation=cv2.INTER_AREA)
    Pattern_imgbytes = cv2.imencode('.png', Resized_Display_Image)[1].tobytes()

    # Display Loaded Image
    Image_Widget = sg.Image(data = Pattern_imgbytes, key="Pattern_Display")
    Pattern_Display_Col = [[Image_Widget]]

    Images_List_Col = NMS_Master_Thumbnails_List


    #  Layout Section
    NMS_Pattern_View_Layout  = [
        [
            sg.Column(Pattern_Display_Col, element_justification='c'), 
            sg.VSeperator(),
            sg.Column(Images_List_Col, element_justification='c', scrollable=True, vertical_scroll_only=True, expand_y=True)
        ]
    ]

    # Create Window
    MS_Win = sg.Window('Camera View Window', NMS_Pattern_View_Layout, location=(NMS_Pattern_View_Screen_Position_Width, NMS_Pattern_View_Screen_Position_Height), size=(NMS_Pattern_View_Width,NMS_Pattern_View_Height), keep_on_top=True, finalize=True)
    return MS_Win, NMS_Pattern_Display_Width, NMS_Pattern_Display_Height


######################
# CC DB DATA
######################

# Camera Control Database Connection
rcv_data = database("camctrl")

# Camera Focus Value
Current_Focus_Val = rcv_data[3]

# Identify Camera In Use
"""
Camera Selector From Value Set In The Database
-:> returns the index valu of the camera selected

Cam1: True or False Value of Camera 1
Cam2: True or False Value of Camera 2
Cam3: True or False Value of Camera 3
"""
def Camera_In_Use(Cam1 = rcv_data[0], Cam2 = rcv_data[1], Cam3 = rcv_data[2]):
    if Cam1 == 1:
        return 0
    if Cam2 == 1:
        return 1
    if Cam3 == 1:
        return 2

# Storing Index Value Of Camera
Selected_Camera = Camera_In_Use()


"""
Camera Test
-> Checks If The Selected Camera Is Available

-:> Returns True When Camera Is Available
-:> Returns False When Camera Is Unavailable

Camera_Index: The Index Value Of The Camera In Use
Camera_Focus: Focus Value To Control Camera Zoom
Test_Popup: Enable/Disables Popup To Show If The Selected Camera Is Available
"""
# Camera Available Test
def Cam_Test(Camera_Index = Selected_Camera, Camera_Focus = Current_Focus_Val, Test_Popup = False):
    cap_Test = cv2.VideoCapture(Camera_Index, cv2.CAP_DSHOW)
    cap_Test.set(cv2.CAP_PROP_FOCUS, Camera_Focus)
    Test_ret,Test_frame = cap_Test.read()
    if Test_ret == True:
        cap_Test.release()
        return True
    else:
        if Test_Popup == True:
            sg.Popup("Camera Check","Problem Detecting Camera.\nPlease SELECT and SAVE An Available Camera In The Camera Setting.", keep_on_top=True)
        cap_Test.release()
        return False

# Run Cam Test Function
Cam_Test(Test_Popup = True)


"""
Camera Control Section
-> Controls Camera In Use
-> Controls Camera Focus
"""
# Camera Set Up Control
def Camera_Control_View(): 

    # Window Metrics
    CC_View_Width = monitor_dimensions["Monitor_1_Width"] - 100
    CC_View_Height = (monitor_dimensions["Monitor_1_Height"] - 100)
    CC_Display_Width = (CC_View_Width - 250)
    CC_Display_Height = (CC_View_Height - 30)
    CC_View_Screen_Position_Width = (monitor_dimensions["Monitor_1_Width"] - CC_View_Width)/2
    CC_View_Screen_Position_Height  = (monitor_dimensions["Monitor_1_Height"] - CC_View_Height)/5

    # Header Text
    Header = [sg.Text("Select A Camera", auto_size_text=True, text_color="white", font="Courier 20", justification="left"), sg.Button("SAVE", button_color=('white', 'green'), enable_events=True,  font=('Courier 10',10), size=(16,1)), sg.Button("CLOSE", button_color=('white', 'red'), enable_events=True,  font=('Courier 10',10), size=(16,1))]

    # Comera Selector
    All_Cams_Selector = [sg.Radio('Camera 1', "CAMERA_SELECTOR", default = rcv_data[0]), sg.Radio('Camera 2', "CAMERA_SELECTOR", default = rcv_data[1]), sg.Radio('Camera 3', "CAMERA_SELECTOR", default = rcv_data[2])]
    Camera_View = [sg.Image(filename="", key="Camera_Control_Display"),sg.VSeperator(), sg.Text('', size=(5,1)),sg.Slider(range=(0, 255), orientation='v', size=(25, 15), default_value=Current_Focus_Val, tick_interval=5, key="-Focus Control-")]

    # List Of Connectable Cameras
    CC_View = [
        # Page Header
        Header,

        # Camera List
        All_Cams_Selector, 

        # Camera View And Slider
        Camera_View
        ]

    # Camera Layout
    Camera_Control_Layout = [[CC_View]]

    # Create Window
    CC_Win = sg.Window('Camera Control Window', Camera_Control_Layout, location=(CC_View_Screen_Position_Width, CC_View_Screen_Position_Height), size=(CC_View_Width,CC_View_Height), keep_on_top=True, finalize=True)
    return CC_Win, CC_Display_Width, CC_Display_Height


"""
Other Setting Section
-> Sets Logging Level
-> Sets Bbox Line Width
-> Sets Bbox Colour
-> Sets Thumbnails Dimensions(Width and Height)
-> Sets Pattern Folder Location
-> Auto-Sets Thumbnails Folder Location
-> Auto-Sets Analysis Results Folder Location
"""
#  Other Settings Used In The App Section
def Other_Setting_View():

    # Window Metrics
    OS_View_Width = monitor_dimensions["Monitor_1_Width"] - 500
    OS_View_Height = (monitor_dimensions["Monitor_1_Height"] - 300)
    OS_Display_Width = (OS_View_Width - 250)
    OS_Display_Height = (OS_View_Height - 30)
    OS_View_Screen_Position_Width = (monitor_dimensions["Monitor_1_Width"] - OS_View_Width)/2
    OS_View_Screen_Position_Height  = (monitor_dimensions["Monitor_1_Height"] - OS_View_Height)/5

    # Other Setting Database Connection
    othset_data = database("othsetctrl")

    # NMS Master Folder
    NMS_Master_Pattern_Folder = f"{othset_data[6]}"
    Origin_Folder = f"{othset_data[9]}"

    # Other Setting Widgets
    OS_Header = [sg.Text("OTHER RELEVANT SETTING",auto_size_text=True, text_color="white", font=("Courier 20", 30), justification="center")]

    # Setting Control
    Count_Down_Timer_Widget = [sg.Text("COUNTDOWN TIMER:", auto_size_text=False, size=(23, 1), text_color="white", font=("Courier", 20), justification="left"), sg.InputText(size=(50, 1), default_text=f"{Count_Down_Timer}", key="-Time_Delay-")]

    Log_Level_Widget = [sg.Text("SELECT LOG LEVEL:", auto_size_text=False, size=(23, 1), text_color="white", font=("Courier", 20), justification="left"), sg.DropDown(['DEBUG', 'INFO','WARNING','ERROR','CRITICAL'], size=(50, 1), default_value=f"{App_Log_Level.upper()}", key="-Set_Log_Level-")]

    Line_Width_Widget = [sg.Text("SELECT BBOX WIDTH:", auto_size_text=False, size=(23, 1), text_color="white", font=("Courier", 20), justification="left"), sg.DropDown(Bbox_Width_List, size=(50, 1), default_value=f"{Bbox_Width_List[Bbox_Line_Width-1]}", key="-Set_Bbox_Width-")]

    Bbox_Line_Color_Widget = [sg.Text("SELECT BBOX COLOR:", auto_size_text=False, size=(23, 1), text_color="white", font=("Courier", 20), justification="left"), sg.DropDown(['BLACK','WHITE','RED','GREEN','BLUE'], size=(50, 1), default_value = f"{Bbox_Color_in_DB.upper()}", key="-Set_Bbox_Color-")]

    Thumbnail_Dimensions_Widget = [sg.Text("THUMBNAIL DIMENSIONS:", auto_size_text=False, size=(23, 1), text_color="white", font=("Courier", 20), justification="left"), sg.DropDown(["50 by 50 Pixels","100 by 100 Pixels","150 by 150 Pixels"], size=(50, 1), default_value = f"{Thumbnail_Width} by {Thumbnail_Height} Pixels", key="-Set_Thumbnail_Dimension-")]

    Pattern_Origin_Folder_Widget = [sg.Text('PATTERN ORIGIN FOLDER:', auto_size_text=False, size=(23, 1), font=("Courier", 20), justification='left'),sg.InputText(f"{Origin_Folder}", enable_events=True, key="-Pattern_Origin_Folder-", disabled=True)]    
    
    Master_Pattern_Folder_Widget = [sg.Text('SELECT PATTERN FOLDER:', auto_size_text=False, size=(23, 1), font=("Courier", 20), justification='left'),sg.InputText(f"{NMS_Master_Pattern_Folder}", enable_events=True, key="-Set_Master_Folder-"), sg.FolderBrowse()]

    OS_Buttons = [sg.Button("SAVE", button_color=('white', 'green'),  font=('Courier 10',15), size=(15,1)),  sg.Button("CLOSE", button_color=('white', 'red'), font=('Courier 10',15), size=(15,1))]

    # Other Setting View  
    OS_View = [
        # Page Header
        OS_Header,

        # Time Delay
        Count_Down_Timer_Widget,

        # Set Log Level
        Log_Level_Widget,

        # Set Bbox Line Width
        Line_Width_Widget,

        # Set Bbox Line Color
        Bbox_Line_Color_Widget,

        # Set Thumbnail Dimension
        Thumbnail_Dimensions_Widget,

        # Show The Current Saved Origin Folder
        Pattern_Origin_Folder_Widget,

        # Set New Pattern Folder
        Master_Pattern_Folder_Widget,

        # Os Control Buttons
        OS_Buttons
        ]

    # Camera Layout
    OS_Layout = [[OS_View]]

    # Create Window
    OS_Win = sg.Window('Other Setting Window', OS_Layout, location=(OS_View_Screen_Position_Width, OS_View_Screen_Position_Height), size=(OS_View_Width,OS_View_Height), keep_on_top=True, finalize=True)
    return OS_Win, OS_Display_Width, OS_Display_Height


"""
View Previous Analysis Section
-> Loads All The Runs For Each Date And Collection
-> Displays Collective Average SSIM
-> Displays Individual Paired SSIM
-> Allows Patterns And Images To Be Viewed
"""
# View App Analysis Results Section
def Analysis_View(Results_Folder_Path = Analysis_Results_Folder):

    # Window Metrics
    Analysis_View_Width = monitor_dimensions["Monitor_1_Width"] - 100
    Analysis_View_Height = (monitor_dimensions["Monitor_1_Height"] - 100)
    Analysis_Display_Width = (Analysis_View_Width - 250)
    Analysis_Display_Height = (Analysis_View_Height - 30)
    Analysis_View_Screen_Position_Width = (monitor_dimensions["Monitor_1_Width"] - Analysis_View_Width)/2
    Analysis_View_Screen_Position_Height  = (monitor_dimensions["Monitor_1_Height"] - Analysis_View_Height)/5


    # ANALYSIS WINDOW WIDGETS

    # Date Widget
    Dates = os.listdir(Results_Folder_Path)

    # If No Analysis Is Available
    if Dates == []:
        Analysis_Date_List = [sg.Text("No Data Available", font=('Courier 30',60), key="No_Analysis_Data")]

        Analysis_View_Layout = [Analysis_Date_List]
    else:
        Analysis_Header = [sg.Text("ANALYSIS DATA", size=(Analysis_Display_Width,1), font=('Courier 20',20), key="Analysis_Header", justification="center")]

        Analysis_Date_List = [[sg.ReadFormButton(f"{Date}", size=(25,1), key=(f"Date_{Date}"))] for Date in Dates]

        # Collection Widget
        All_Collection_List = list()

        # Runs Widget
        All_Runs_List = list()
        
        All_Collection_List.append(sg.Column(Analysis_Date_List, scrollable=True, vertical_scroll_only=True, size=(300,200), key="Analysis_Date_Column"))
        All_Collection_List.append(sg.VSeperator())

        for Date in Dates:
            Analysis_Collection_Button_List = [[sg.Button(f"{Collection_Name}", size=(60,1), key=(f"Collection_{Collection_Name}"))] for Collection_Name in os.listdir(f"{Results_Folder_Path}/{Date}")]
            
            if Date == os.listdir(f"{Results_Folder_Path}")[0]:
                Col = sg.Column(Analysis_Collection_Button_List, scrollable = True, vertical_scroll_only=True, expand_x=True, size=(600,200), key=f"Collection_{Date}", visible=True)
            else:
                Col = sg.Column(Analysis_Collection_Button_List, scrollable = True, vertical_scroll_only=True, expand_x=True, size=(600,200), key=f"Collection_{Date}", visible=False)
            
            # Add Element To List 
            All_Collection_List.append(Col)

        #########################################
        # Image Display Control Buttons Section #
        #########################################

        # # Select First Date Folder
        # First_Date = os.listdir(f"{Results_Folder_Path}")[0]

        # # Select Collection Folder
        # Collection = os.listdir(f"{Results_Folder_Path}/{First_Date}")[0]

        # # Select Run Folder 
        # Runs = os.listdir(f"{Results_Folder_Path}/{First_Date}/{Collection}")

        ##########################
        # Image Display Section
        ##########################

        # Collect All Runs Available
        for Date in tqdm(Dates, desc = "Fetching Display Data"):
            for Collection in os.listdir(f"{Results_Folder_Path}/{Date}"):
                for Test_Run in os.listdir(f"{Results_Folder_Path}/{Date}/{Collection}"):
                    
                    # Full Path To Runs Folder
                    Runs_Folder_Path = f"{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}"

                    # PROCESSING ANNOTATION FILE
                    try:    
                        # Set Annoatation Path
                        Runs_Annotation_Path = f"{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/ANNOTATION/Annotation.csv"

                        # Read Annotation File
                        df = pd.read_csv(Runs_Annotation_Path)
                        
                        # Annotation Show
                        df.drop(['Image_Name','Pattern_Name'], inplace=True, axis=1)

                    except Exception as e:
                        Runs_Annotation = None

                    # No of Pattern and Images Folder
                    Item_List = [x for x in os.listdir(Runs_Folder_Path) if x != "ANNOTATION"]
                    Item_List.sort(key=natural_keys)
                    Item_Ids = [x.split("_")[0] for x in Item_List]
                    Ids = sorted(set(Item_Ids))

                    # Building A list Of Patterns And Images
                    Data_View = list()
                    Data_View_Sublist = list()

                    for Id in tqdm(Ids, desc = f"Loading For {Results_Folder_Path}/{Date}/{Collection}/{Test_Run}"):
                        try:
                            New_df = df[df["SN"] == int(Id)]
                            New_df.reset_index(drop=True, inplace=True)
                            SSIM_VALUE  = New_df.iat[0, 1]
                        except:
                            pass
                        Data_View_Sublist.append(sg.Button(f"", image_filename=f"{Runs_Folder_Path}/{Id}_Image.png", image_size=(150, 150), border_width=0, key=f"{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/{Id}_Image.png")) 
                        Data_View_Sublist.append(sg.Button(f"", image_filename=f"{Runs_Folder_Path}/{Id}_Pattern.png", image_size=(150, 150), border_width=0, key=f"{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/{Id}_Pattern.png"))
                        Data_View_Sublist.append(sg.VSeperator(key=f"{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/Seperator_{Id}"))
                        
                        if Id == "01":
                            try:
                                Avg_df = df.loc[df["SN"] == len(df)]
                                Avg_df.reset_index(drop=True, inplace=True)
                                FINAL_SSIM = Avg_df.iat[0, 2]
                                Data_View.append(sg.Text(f"{Date}\n{Collection}\n{Test_Run}\nSSIM: {round(FINAL_SSIM,4)}", auto_size_text=True, font=('Courier 16',16), size=(18,4), key=f"Run_Header_{Results_Folder_Path}_{Date}_{Collection}_{Test_Run}", justification="center"))
                                Data_View.append(sg.Column([Data_View_Sublist, [sg.Text(f"SSIM VALUE: {SSIM_VALUE}", justification="center"), sg.Button('FULL VIEW', key=f"{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/{Id}_FullScale_Image.png,{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/{Id}_FullScale_Pattern.png")]]))
                            except Exception as e:
                                Data_View.append(sg.Text(f"{Date}\n{Collection}\n{Test_Run}", auto_size_text=True, font=('Courier 16',16), size=(18,3), key=f"Run_Header_{Results_Folder_Path}_{Date}_{Collection}_{Test_Run}", justification="center"))
                                Data_View.append(sg.Column([Data_View_Sublist, [sg.Text("NO SSIM AVAILABLE", justification="center"), sg.Button('FULL VIEW', key=f"{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/{Id}_FullScale_Image.png,{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/{Id}_FullScale_Pattern.png")]]))
                            Data_View_Sublist.clear()
                        else:
                            try:
                                Data_View.append(sg.Column([Data_View_Sublist, [sg.Text(f"SSIM VALUE: {SSIM_VALUE}", justification="center"), sg.Button('FULL VIEW', key=f"{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/{Id}_FullScale_Image.png,{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/{Id}_FullScale_Pattern.png")]]))
                            except:
                                Data_View.append(sg.Column([Data_View_Sublist, [sg.Text("NO SSIM AVAILABLE", justification="center"), sg.Button('FULL VIEW', key=f"{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/{Id}_FullScale_Image.png,{Results_Folder_Path}/{Date}/{Collection}/{Test_Run}/{Id}_FullScale_Pattern.png" )]]))
                            Data_View_Sublist.clear()
                
                    All_Runs_List.append(Data_View)


        #  Layout Section
        Analysis_View_Layout  = [
            Analysis_Header,
            # [
            #     sg.Column([All_Collection_List])
            # ],
            [
                sg.Column(
                    ([
                        sg.Column([Run_List], scrollable=True, size=(Analysis_View_Width - 15,200), element_justification = "c")
                        ] for index, Run_List in enumerate(tqdm(All_Runs_List, desc = "Loading Display"))), scrollable = True, vertical_scroll_only = True, expand_x = True, expand_y = True
                )
            ]
        ]

    # Create Window
    ANALYSIS_Win = sg.Window('Analysis View Window', Analysis_View_Layout, location=(Analysis_View_Screen_Position_Width, Analysis_View_Screen_Position_Height), size=(Analysis_View_Width,Analysis_View_Height), keep_on_top=True, finalize=True)
    return ANALYSIS_Win, Analysis_Display_Width, Analysis_Display_Height


"""
View Previous Analysis Images
-> Allows Images Clicked In The Previous Analysis Section To Be Displayed
-> Allows User To View The Full Image With The Bbox Drawn In Position

Dual: This is used to specify whether the function is to display as single picture or 
multiple pictures, Dual == False(Default) specify the window opens and displays a single
image, Dual == True, specifies that the window will be displaying two images side by side.

Image Path: This is used when Dual == False and specifies the path to the single image

kwargs: This keyword arguement that expects the path to the two images with keywords Img1 
for the camera capture and Img2 for the pattern.
"""
# View Image From Analysis Section When Clicked
def Image_View_Win(Image_Path = "", Dual = False, **kwargs):

    # Display Full Scale Images Side By Side
    if(Dual == True):

            # Window Metrics
        Image_View_Width = monitor_dimensions["Monitor_1_Width"] - 100
        Image_View_Height = monitor_dimensions["Monitor_1_Height"] - 100
        Image_Display_Width = (Image_View_Width - 250)
        Image_Display_Height = (Image_View_Height - 30)
        Image_View_Screen_Position_Width = (monitor_dimensions["Monitor_1_Width"] - Image_View_Width)/2
        Image_View_Screen_Position_Height  = (monitor_dimensions["Monitor_1_Height"] - Image_View_Height)/5

        # Show Screen Dmensions
        Split_Screen_Width = Image_View_Width/2
        
        # Show Image 1 Dimensions
        Image_1 = cv2.imread(kwargs["Img1"])
        Image_1_Dimension = Image_1.shape

        # Show Image 2 Dimensions
        Image_2 = cv2.imread(kwargs["Img2"])
        Image_2_Dimension = Image_2.shape

        # Identify Max Width and Height
        Max_Img_Height = max(Image_1_Dimension[0],Image_2_Dimension[0])
        Max_Img_Width = max(Image_1_Dimension[1],Image_2_Dimension[1])

        # Create New Image Dimensions
        Img1_Height = int(round((Image_1_Dimension[0]/Max_Img_Height) * Image_View_Height))
        Img1_Width = int(round((Image_1_Dimension[1]/Max_Img_Width) * Split_Screen_Width))

        # Resize Image 
        Resized_Image1 = cv2.resize(Image_1, (Img1_Width,Img1_Height), interpolation = cv2.INTER_AREA)
        Resized_img1_bytes = cv2.imencode('.png', Resized_Image1)[1].tobytes()

        # Create New Pattern Dimensions
        Img2_Height = int(round((Image_2_Dimension[0]/Max_Img_Height) * Image_View_Height))
        Img2_Width = int(round((Image_2_Dimension[1]/Max_Img_Width) * Split_Screen_Width))

        # Resize Pattern
        Resized_Image2 = cv2.resize(Image_2, (Img2_Width, Img2_Height), interpolation = cv2.INTER_AREA) 
        Resized_img2_bytes = cv2.imencode('.png', Resized_Image2)[1].tobytes()

        # Image Display Widget
        Image_1_Widget = [
            sg.Image(data = Resized_img1_bytes, size=(Split_Screen_Width, Image_View_Height), key="FullScale_Image"),
            sg.VSeperator(),
            sg.Image(data = Resized_img2_bytes, size=(Split_Screen_Width, Image_View_Height), key="FullScale_Pattern")
            ]

        # Arrangement of Widgets on The Display 
        Widget_Layout = [sg.Column([
            Image_1_Widget
            ], scrollable = True, expand_x = True, expand_y = True)]

        Image_Display_Layout = [[ Widget_Layout ]]

        # Get Image 1 Name
        Image_1_split = kwargs["Img1"].split("/")
        Image_1_Name = Image_1_split[-1]
        
        # Get Image 2 Name
        Image_2_split = kwargs["Img2"].split("/")
        Image_2_Name = Image_2_split[-1]

        # Create Window
        IMAGE_Win = sg.Window(f"Shwoing {Image_1_Name} and {Image_2_Name}", Image_Display_Layout, location=(Image_View_Screen_Position_Width, Image_View_Screen_Position_Height), size=(Image_View_Width,Image_View_Height), keep_on_top=True, finalize=True)
        return IMAGE_Win, Image_Display_Width, Image_Display_Height


    # Display Clicked Cropped Images
    elif (Dual == False):
        # Get Image Properties
        Read_Img = cv2.imread(Image_Path)
        Img_Dimensions = Read_Img.shape
        
        # Window Metrics
        if (Img_Dimensions[0] < monitor_dimensions["Monitor_1_Height"]) or (Img_Dimensions[1] < monitor_dimensions["Monitor_1_Width"]):
            Image_View_Width = Img_Dimensions[1] + 30
            Image_View_Height = Img_Dimensions[0] + 30
            Image_Display_Width = Img_Dimensions[1]
            Image_Display_Height = Img_Dimensions[0]
            Image_View_Screen_Position_Width = (monitor_dimensions["Monitor_1_Width"] - Image_View_Width)/2
            Image_View_Screen_Position_Height  = (monitor_dimensions["Monitor_1_Height"] - Image_View_Height)/5

        # Image Display Widget
        Image_Widget = [sg.Image(filename=Image_Path, key="Analysis_Image_Viewer")]
        
        # Arrangement of Widgets on The Display 
        Widget_Layout = [
            Image_Widget
            ]

        Image_Display_Layout = [[ Widget_Layout ]]

        Image_Path_Split = Image_Path.split("/")
        Image_Name = Image_Path_Split[-1]

        # Create Window
        IMAGE_Win = sg.Window(f"{Image_Name}", Image_Display_Layout, location=(Image_View_Screen_Position_Width, Image_View_Screen_Position_Height), size=(Image_View_Width,Image_View_Height), keep_on_top=True, finalize=True)
        return IMAGE_Win, Image_Display_Width, Image_Display_Height
    

"""
App Start Image Capture Window
-> Displays Image Captured
-> Displays Section Of The Image SSIM Is bein Carried Out On
-> Displays Individual SSIM
-> Displays Overall SSIM
-> Displays Countdown Timer
-> Displays Pattern Count
-> Displays Collection Count

-:> Retunrs the window, window height, window width
"""
# MAIN APP SECTION
def Main_App_Section():

    # Window Metrics
    MAS_View_Width = monitor_dimensions["Monitor_1_Width"] - 100
    MAS_View_Height = (monitor_dimensions["Monitor_1_Height"] - 150)
    MAS_Display_Width = (MAS_View_Width - 250)
    MAS_Display_Height = (MAS_View_Height - 30)
    MAS_View_Screen_Position_Width = (monitor_dimensions["Monitor_1_Width"] - MAS_View_Width)/2
    MAS_View_Screen_Position_Height  = (monitor_dimensions["Monitor_1_Height"] - MAS_View_Height)/5

    ###### Main App Widgets #####

    # Main App Buttons
    MAS_Restart_Button = [sg.Button("START", button_color=('white', 'green'), enable_events=True, font=('Courier 10',15), size=(15,1), key="-MAS_Start_Button-")]

    MAS_Manual_Button = [sg.Button("MANUAL", enable_events=True, font=("Courier 10",15), size=(15,1), key="-MAS_Manual_Button-")]

    MAS_Stop_Button = [sg.Button("STOP", button_color=('white', 'brown'), enable_events=True, font=('Courier 10',15), size=(15,1), key="-MAS_Stop_Button-")]

    MAS_Exit_Button = [sg.Button("EXIT", button_color=('white', 'red'), enable_events=True, font=('Courier 10',15), size=(15,1), key="-MAS_Exit_Button-")]

    MAS_SingleRun_Button = [sg.Button("SINGLE RUN", button_color=('white','black'), enable_events=True, font=('Courier 10',15), size=(15,1), key="-MAS_SingleRun_Button-")]

    MAS_Buttons_Widget = [sg.Column([MAS_Restart_Button, MAS_Manual_Button, MAS_SingleRun_Button, MAS_Stop_Button, MAS_Exit_Button], background_color="white")]

    # Timer Section
    MAS_Timer_Text = [sg.Text("Timer", size=(15, 1), text_color='black', background_color='white', font=('Courier 10', 15), justification='center')]

    MAS_Timer_Time = [sg.Text('00:00', size=(15, 1), text_color='black', background_color='white', font=('Courier 10', 15), justification="center", key="-MAS_Timer_Time-")]   

    MAS_Timer_Widget = [sg.Column([MAS_Timer_Text, MAS_Timer_Time], background_color="white")]

    # Individual SSIM Result
    MAS_Single_SSIM_Text = [sg.Text("Current SSIM", size=(15, 1), text_color='black', background_color='white', font=('Courier 10', 15), justification='center')]

    MAS_Single_SSIM_Result = [sg.Text("0.000", size=(15, 1), text_color='black', background_color='white', font=('Courier 10', 15), justification='center', key="-MAS_Single_SSIM_Result-")]

    MAS_Individual_SSIM_Widget = [sg.Column([MAS_Single_SSIM_Text, MAS_Single_SSIM_Result], background_color="white")]

    # Current Overall SSIM Result
    MAS_Current_Overall_SSIM_Text = [sg.Text("Collective SSIM", size=(15, 1), text_color='black', background_color='white', font=('Courier 10', 15), justification='center')]

    MAS_Current_Overall_SSIM_Result = [sg.Text("0.000", size=(15, 1), text_color='black', background_color='white', font=('Courier 10', 15), justification='center', key="-MAS_Overall_SSIM_Result-")]

    MAS_Current_Overall_SSIM_Widget = [sg.Column([MAS_Current_Overall_SSIM_Text,MAS_Current_Overall_SSIM_Result], background_color="white")]

    # Pattern Count
    MAS_Pattern_Text = [sg.Text("Pattern Count", size=(15, 1), text_color='black', background_color='white', font=('Courier 10', 15), justification='center')]

    MAS_Pattern_Count = [sg.Text(int(Pattern_Count) , size=(15, 1), text_color='black', background_color='white', font=('Courier 10', 15), justification='center', key="-MAS_Pattern_Count-")]

    MAS_Pattern_Widget = [sg.Column([MAS_Pattern_Text,MAS_Pattern_Count], background_color="white")]

    # Collection Count
    MAS_Collection_Text = [sg.Text("Collection Count", size=(15, 1), text_color='black', background_color='white', font=('Courier 10', 15), justification='center')]

    MAS_Collection_Count = [sg.Text("0", size=(15, 1), text_color='black', background_color='white', font=('Courier 10', 15), justification='center', key="-MAS_Collection_Count-")]

    MAS_Collection_Widget = [sg.Column([MAS_Collection_Text,MAS_Collection_Count], background_color="white")]

    # Display Divider
    MAS_Divider = sg.VSeperator()

    # Camera Display 
    MAS_Camera_Display = [sg.Image(filename="", key="-MAS_Camera_Display-")]

    # Left Display Section
    MAS_Left = [
        MAS_Buttons_Widget,

        MAS_Timer_Widget,

        MAS_Individual_SSIM_Widget,
        
        MAS_Current_Overall_SSIM_Widget,

        MAS_Pattern_Widget,

        MAS_Collection_Widget
    ]

    # Right Display Section
    MAS_Right = [MAS_Camera_Display]

    #  Layout Section
    MAS_View_Layout  = [[sg.Column(MAS_Left, element_justification='c'), MAS_Divider, sg.Column(MAS_Right, element_justification='c')]]

    # Create Window
    MAS_Win = sg.Window('Main App Window', MAS_View_Layout, location=(MAS_View_Screen_Position_Width, MAS_View_Screen_Position_Height), size=(MAS_View_Width,MAS_View_Height), keep_on_top=True, finalize=True)
    return MAS_Win, MAS_Display_Width, MAS_Display_Height


"""
-> Creates Folder Containing Each Iteration of collections
-> Creates Collection Folder

Collection: The colection folder name, defaults to 'Default Collection'
Folder_Name: The name of the folder, default name is 'New Folder'
Count: Used to create an incremental newer version of the 'New Folder'
"""
# Create Storage Folder
def Folder_Create(Parent_Folder):
    date = dt.datetime.date(dt.datetime.now())
    # date = dt.datetime.strftime(dt.datetime.now(), '%H-%M-%S')
    os.makedirs(f"{Parent_Folder}/{date}", exist_ok=True)
    return f"{Parent_Folder}/{date}"

"""
Collection Folder Creator
-> Create The Collection Folder Names for default settings.

-:> Returns The Auto-Generated Collection Name
-:> Returns the storage path

Storage_Path: The path to the results folder in which the collection will be stored
Collection_Name: The name of the folder where the collection is stored, default name is 'Default_Collection'
Count: Gives each folder a unique number for easy i dentification
"""
# Create Collection
def Create_Collection(Storage_Path, Collection_Name = "Default_WinSSIM", Count=0):
    if Collection_Name in os.listdir(Storage_Path):
        Count += 1
        Name_List = Collection_Name.split("_")
        Collection_Name = f"{Name_List[0]}_{Name_List[1]}_{Count}"
        return Create_Collection(Storage_Path,Collection_Name,Count)
    else:
        os.makedirs(f"{Storage_Path}/{Collection_Name}")
        sg.Popup(f"Using Default Collection Name {Collection_Name} at Location {Storage_Path}",  keep_on_top=True, background_color="black")
    return Collection_Name,Storage_Path


"""
Refresh Thumbnails List
-> Auto Updates List of Thumbnails
-> Auto Update Display of Thumbnails
-> Auto Update Pattern Image on Display
-> Draw Bounding Box Around Items In Focus

-:> Returns A list of containing Bboxed_Pattern_Image, Cropped_Section, PXmin, PYmin, PXmax, PYmax

window: Represents the name of the pysimplegui window where this function is called
window_Width: The width of the window
window_Height: The height of the window

Trigger_event: This is the value of the event that triggers this function, usually 
this will be the name of the thumbnail image that has been clicked around which a 
bbox will be applied to show that it is active.

Pattern_File_Path: This is the path to the folder containing all the mirror standard pattern images
Thumbnail_File_Path: This is the path to the thumbnails folder containing the thumbnail Images
Origin_File_Path: The Path To The Origin Folder Containing The Original Pattern Images
Image_List: This is the list of all the thumbnail image names, default value is none
Thumbnail_Width: This the width that the thumbnail image will be reshaped to
Thumbnail_Height: This is the height that the thumbnail image will be reshaped to
Bbox: Control display of bbox on the image (relevant to the MAIN APP SECTION), the available options are "Active" or "Inactive"
Refresh: Controls if the thumbnail images should be refreshed or not
"""
# Refresh Thumbnails
def Thumbnails_Refresh(window, window_Width, window_Height, Trigger_event, Pattern_File_Path, Thumbnail_File_Path, Origin_File_Path = None, Bbox = "Inactive", Refresh=True, Image_List = None, Thumbnail_Width=Thumbnail_Width, Thumbnail_Height=Thumbnail_Height):
    
    # Refresh Master Folder
    othset_data = database("othsetctrl")
    NMS_Master_Thumbnails_Folder = f"{othset_data[7]}"

    if Refresh == True:
        # Update All Thumbnails
        Thumbnails_Images_Path_List = [f"{NMS_Master_Thumbnails_Folder}/{image}" for image in Image_List]
        for Thumbnail_Image_Path in Thumbnails_Images_Path_List:
            Path_Split = Thumbnail_Image_Path.split("/")
            Updated_Thumbnail = cv2.imread(Thumbnail_Image_Path)
            Thumbnail_Resize = cv2.resize(Updated_Thumbnail,(Thumbnail_Width,Thumbnail_Height), interpolation=cv2.INTER_AREA)
            Updated_Thumbnail_imgbytes = cv2.imencode('.png', Thumbnail_Resize)[1].tobytes()
            window[Path_Split[-1]].update(image_data=Updated_Thumbnail_imgbytes)
        logger.debug("Thumbnail Refresh Complete")

    if Trigger_event != None:
        # Image Thumbnail In View
        Thumbnail_Image = cv2.imread(Thumbnail_File_Path)

        # Thumbnail Bbox Parameters
        Thumbnail_Bbox_Start_Point = (0,0)
        Thumbnail_Bbox_End_Point = (Thumbnail_Width,Thumbnail_Height)
        color = Bbox_Line_Color
        line_width = Bbox_Line_Width

        # Highlight Image with Bbox
        Thumbnail_Image_Copy = copy.deepcopy(Thumbnail_Image)
        Thumbnail_Copy_Resize = cv2.resize(Thumbnail_Image_Copy,(Thumbnail_Width,Thumbnail_Height), interpolation=cv2.INTER_AREA)
        Bbox_Thumbnail_Image_Copy = cv2.rectangle(Thumbnail_Copy_Resize, Thumbnail_Bbox_Start_Point, Thumbnail_Bbox_End_Point, color, line_width)
        Bbox_Current_Thumbnail_imgbytes_Copy = cv2.imencode('.png', Bbox_Thumbnail_Image_Copy)[1].tobytes()
        logger.debug("="*30)
        logger.debug(Trigger_event)
        logger.debug("="*30)
        window[Trigger_event].update(image_data=Bbox_Current_Thumbnail_imgbytes_Copy)
        logger.debug("Image Thumbnail Highlighted")
        
    # Bbox Display Control
    if Bbox == "Inactive":

        # Update displayed Image
        Pattern_Image = cv2.imread(Pattern_File_Path)
        Resized_Pattern_Image = cv2.resize(Pattern_Image, (window_Width, window_Height), interpolation=cv2.INTER_AREA)
        Current_Pattern_imgbytes = cv2.imencode('.png', Resized_Pattern_Image)[1].tobytes()
        window['Pattern_Display'].update(data=Current_Pattern_imgbytes)
        logger.debug("Image Displayed")

    elif Bbox == "Active":
        DB_Data = database("nmsctrl")

        # Synched Bbox Parameters
        PXmin = int(MAS_Data[6])
        PYmin = int(MAS_Data[8])
        PXmax = int(MAS_Data[7])
        PYmax = int(MAS_Data[9])

        # Bbox Parameters
        Start_point = (PXmin,PYmin)
        End_point = (PXmax,PYmax)
        color = Bbox_Line_Color
        line_width = Bbox_Line_Width

        # Update displayed Image
        Pattern_Image = cv2.imread(Pattern_File_Path)

        print(f"{Origin_File_Path}\n{Pattern_File_Path}\n{Thumbnail_File_Path}")

        # Get Cropped Section
        Pattern_Image_Copy = copy.deepcopy(Pattern_Image)
        Cropped_Section = Pattern_Image_Copy[PYmin:PYmax, PXmin:PXmax]

        # Update Image To Window
        if Origin_File_Path == None:
            Bboxed_Pattern_Image = cv2.rectangle(Pattern_Image, Start_point, End_point, color, line_width)
            Bboxed_Pattern_Image = cv2.imread(Origin_File_Path)
            Resized_Pattern_Image = cv2.resize(Bboxed_Pattern_Image, (window_Width, window_Height), interpolation=cv2.INTER_AREA)
            Current_Pattern_imgbytes = cv2.imencode('.png', Resized_Pattern_Image)[1].tobytes()
            window['Pattern_Display'].update(data=Current_Pattern_imgbytes)
            logger.debug("Bboxed Image Displayed")
            return [Bboxed_Pattern_Image, Cropped_Section, PXmin, PYmin, PXmax, PYmax]
        
        else:
            # Update Display With Origin Image
            Next_Origin_Image = cv2.imread(Origin_File_Path)
            Resized_Origin_Image = cv2.resize(Next_Origin_Image, (window_Width, window_Height), interpolation=cv2.INTER_AREA)
            Next_Origin_imgbytes = cv2.imencode('.png', Resized_Origin_Image)[1].tobytes()
            window['Pattern_Display'].update(data=Next_Origin_imgbytes)
            logger.debug(f"Bboxed Image Displayed updated display Image to {Origin_File_Path}")

            Bboxed_Pattern_Image = cv2.rectangle(Pattern_Image, Start_point, End_point, color, line_width)
            return [Bboxed_Pattern_Image, Cropped_Section, PXmin, PYmin, PXmax, PYmax]


"""
-> Captures New Mirror Standards In Batch Using Interval Set In Camera Control
-> Stores Images to Pattern Folder currently in use by default 
and allows user to set new storage destination if required.

-:> Returns Created Window, Window Height, Window Width
"""
# Batch Image Capture Section
def Batch_Capture():

    # Window Metrics
    BC_View_Width = monitor_dimensions["Monitor_1_Width"] - 100
    BC_View_Height = (monitor_dimensions["Monitor_1_Height"] - 100)
    BC_Display_Width = (BC_View_Width - 350)
    BC_Display_Height = (BC_View_Height - 30)
    BC_View_Screen_Position_Width = (monitor_dimensions["Monitor_1_Width"] - BC_View_Width)/2
    BC_View_Screen_Position_Height  = (monitor_dimensions["Monitor_1_Height"] - BC_View_Height)/5 

    # Controls Header
    BC_Header = [sg.Text("CONTROLS", font=("Courier 20",20),  relief=sg.RELIEF_RIDGE)]

    # Folder Browser
    Folder_Selector = [
        sg.Text("Folder:", font=("Courier 10", 10), justification = "left"),
        sg.InputText("No Folder Selected", font=("Courier 10",10), enable_events=True, size = (18,1), justification = "left", key="Selected_Folder_Path"),
        sg.FolderBrowse()
        ]
    
    # Camera Display
    BC_Cam_Display = [sg.Image(filename="", key="-BC_Camera_Display-", size=(230,230), pad=(10,10))]

    # Image Capture Display
    BC_Img_Cap = [sg.Image(filename="", key="-BC_Image_Capture-")]

    # Start Button
    BC_Start_Button = [sg.Button("START", button_color=("white","green"), enable_events=True, font=("Courier 20",20), size=(15,2))]
    
    # Stop Button
    BC_Stop_Button = [sg.Button("STOP", button_color=("white","brown"), enable_events=True, font=("Courier 20",20), size=(15,2))]

    # Close Button
    BC_Close_Button = [sg.Button("CLOSE", button_color=("white","red"), enable_events=True, font=("Courier 20",20), size=(15,1))]

    # Timer and Counter For The Number of NMS Images Captured
    BC_Text_Data = [
        sg.Text("00:00", font=("Courier 30", 30), background_color="white", text_color="black", size = (6,1), justification = "center", key="-Timer-"), 
        sg.Text("000", font=("Courier 30", 30), background_color="white", text_color="black", size = (4,1), justification = "center", key="-Counter-")
        ] 

    Left_Side = [
        BC_Header,
        Folder_Selector,
        BC_Start_Button,
        BC_Text_Data,
        BC_Stop_Button,
        BC_Cam_Display,
        BC_Close_Button
        ]

    Right_Side = [BC_Img_Cap]

    BC_Layout = [[sg.Column(Left_Side, element_justification='c'), sg.VSeperator(), sg.Column(Right_Side, element_justification='c')]]

    # Create Window
    BC_Win = sg.Window('Batch Capture Window', BC_Layout, location=(BC_View_Screen_Position_Width, BC_View_Screen_Position_Height), size=(BC_View_Width,BC_View_Height), keep_on_top=True, finalize=True)
    return BC_Win, BC_Display_Width, BC_Display_Height

# Batch Display Pattern Section
def Batch_Capture_Pattern(Pattern_Source = "", Default_Pattern = "", Monitor_Count = number_of_monitors):

    if Default_Pattern == "":

        # Get Default Pattern From Source File
        if Pattern_Source == "":
            sg.popup("The Default Pattern Is Not Set")

        else:

            # Try Getting First Pattern File
            try:
                # Select Thumbnail File To be highlighted
                Pattern_Files = os.listdir(Pattern_Source)
                Pattern_Files.sort(key=natural_keys)

                # Refresh Default Display Pattern
                Default_Pattern = f"{Pattern_Source}/{Pattern_Files[0]}"
            
            except Exception as e:
                sg.popup(f"Error While Getting Pattern Folder: {e}")


    else:

        # Pattern Control Section
            if Monitor_Count < 2:

                # Window Metrics
                BCP_Pattern_View_Width = monitor_dimensions["Monitor_1_Width"]
                BCP_Pattern_View_Height = (monitor_dimensions["Monitor_1_Height"])
                BCP_Pattern_Display_Width = BCP_Pattern_View_Width - 50
                BCP_Pattern_Display_Height = BCP_Pattern_View_Height - 50
                BCP_Pattern_View_Screen_Position_Width = (monitor_dimensions["Monitor_1_Width"] - BCP_Pattern_View_Width)/2
                BCP_Pattern_View_Screen_Position_Height  = (monitor_dimensions["Monitor_1_Height"] - BCP_Pattern_View_Height)/5
            
            else:

                # Window Metrics
                BCP_Pattern_View_Width = (monitor_dimensions["Monitor_2_Width"])
                BCP_Pattern_View_Height = (monitor_dimensions["Monitor_2_Height"])
                BCP_Pattern_Display_Width = BCP_Pattern_View_Width - 50
                BCP_Pattern_Display_Height = BCP_Pattern_View_Height - 50
                BCP_Pattern_View_Screen_Position_Width = monitor_dimensions["Monitor_1_Width"] + ((monitor_dimensions["Monitor_2_Width"] - BCP_Pattern_View_Width)/2)
                BCP_Pattern_View_Screen_Position_Height  = (monitor_dimensions["Monitor_2_Height"] - BCP_Pattern_View_Height)/5


            # Pattern Display Section
            try:
                Display_Image = cv2.imread(f"{Default_Pattern}")
                Resized_Display_Image = cv2.resize(Display_Image, (BCP_Pattern_Display_Width, BCP_Pattern_Display_Height),interpolation=cv2.INTER_AREA)
                Pattern_imgbytes = cv2.imencode('.png', Resized_Display_Image)[1].tobytes()
            except:
                sg.popup("Invalid Folder Contents",title="Folder Content Error", keep_on_top=True)
                return None

            # Display Loaded Image
            Image_Widget = sg.Image(data = Pattern_imgbytes, key="Pattern_Display")
            Pattern_Display_Col = [[Image_Widget]]


            #  Layout Section
            Batch_Capture_Pattern_Layout  = [
                [
                    sg.Column(Pattern_Display_Col, element_justification='c')
                ]
            ]

            # Create Window
            BCP_Win = sg.Window('Batch Pattern Window', Batch_Capture_Pattern_Layout, location=(BCP_Pattern_View_Screen_Position_Width, BCP_Pattern_View_Screen_Position_Height), size=(BCP_Pattern_View_Width,BCP_Pattern_View_Height), keep_on_top=True, finalize=True)
            BCP_Win.Maximize()
            return BCP_Win, BCP_Pattern_Display_Width, BCP_Pattern_Display_Height

# App Main Section
if __name__ == '__main__':

    #  Minimum Monitor Requirement Check
    if number_of_monitors == 1:
        logger.info("Using Single Monitor Mode")

    if number_of_monitors > 1:
        logger.info("Using Dual Monitor Mode")
    
    # Start Main Program 
    try:
        HOME_WIN = Home_Win()

        # Home Window Variables
        Activate = True
        Thread_Control = False
        Collection_Count = 0
        Number_of_Patterns = copy.deepcopy(Pattern_Count)

        # Event Loop
        while True:
            home_event, home_values = HOME_WIN.read()

            # New Mirror Standard
            if home_event == "Mirror Standard Settings":

                # Check Camera Availability
                if Cam_Test(Camera_Index = Selected_Camera) == True:
                    # Start Camera
                    cap = cv2.VideoCapture(Selected_Camera, cv2.CAP_DSHOW)
                    cap.set(cv2.CAP_PROP_FOCUS, Current_Focus_Val)
                    
                    # Hiding Home Window
                    HOME_WIN.Hide()

                    # NMS Camera Window
                    NMS_CAM_VIEW_WIN, nms_cam_Width, nms_cam_Height = NMS_Cam_View()
                    logger.debug("Opening New Mirror Standard Camera View")

                    # Get Default Pattern
                    Thumbnail_Files = os.listdir(NMS_Master_Thumbnails_Folder)
                    Thumbnail_Files.sort(key=natural_keys)

                    # Other Setting Database Connection
                    othset_data = database("othsetctrl")

                    # NMS Master Folder
                    NMS_Master_Pattern_Folder = f"{othset_data[6]}"
                    Default_Pattern = f"{NMS_Master_Pattern_Folder}/{os.listdir(NMS_Master_Thumbnails_Folder)[0]}"

                    # NMS Pattern Window
                    NMS_PATTERN_VIEW_WIN, nms_pattern_Width, nms_pattern_Height = NMS_Pattern_View(Default_Pattern=Default_Pattern)
                    logger.debug("Opening New Mirror Standard Pattern View")

                    # Parameters State
                    cam_view = True
                    Active_Stream = True
                    pattern_view = True
                    Pattern_File_Path = Default_Pattern
                    Thumbnail_File_Path= Default_Thumbnail
                    Align_Crop_Dimensions = False
                    Crop = f"{Crop_Status}"
                    Sync = f"{Sync_Status}"

                    # MultiBbox Defaults
                    nmsctrl_data = database("nmsctrl")
                    Mode = nmsctrl_data[12]
                    Multi_Crop = nmsctrl_data[11]
                    Window_Read = False

                    # Initial Pattern In View
                    Pattern_Image = cv2.imread(f"{Pattern_File_Path}")

                    logger.debug("Auto Start Camera Stream")

                    while cam_view:
                        nms_cam_view_event, nms_cam_view_values = NMS_CAM_VIEW_WIN.read(timeout=10)

                        # Taking Pictures
                        if (nms_cam_view_event == "TAKE PICTURE") and (cam_view == True):
                            Active_Stream = False
                            logger.debug("Stopping Camera Stream")
                            ret, frame = cap.read()
                            resized_capture = cv2.resize(frame, (nms_cam_Width, nms_cam_Height), interpolation=cv2.INTER_AREA)
                            camera_capturebytes = cv2.imencode('.png',resized_capture)[1].tobytes()
                            NMS_CAM_VIEW_WIN['camera'].update(data=camera_capturebytes)
                            logger.debug("Taking A Picture")

                        # Start Stream
                        if (nms_cam_view_event == "START STREAM"):
                            Active_Stream = True
                            logger.debug("Manual Start Camera Stream")

                        # On Start Stream Video From Camera
                        if (Active_Stream == True) and (cam_view == True):
                            ret, frame = cap.read()
                            live_feed_resized = cv2.resize(frame, (nms_cam_Width, nms_cam_Height), interpolation=cv2.INTER_AREA)
                            imgbytes = cv2.imencode('.png', live_feed_resized)[1].tobytes()
                            NMS_CAM_VIEW_WIN['camera'].update(data=imgbytes)

                        # Closing NMS CAM View Window
                        if (nms_cam_view_event == sg.WIN_CLOSED) or (nms_cam_view_event == "CLOSE"):
                            logger.debug("Closing New Mirror Standard Camera View")
                            
                            # Unset Camera Stream
                            cap.release()
                            
                            # Close Camera View
                            NMS_CAM_VIEW_WIN.close()
                            cam_view = False

                            # Close Pattern View
                            if pattern_view == True:
                                NMS_PATTERN_VIEW_WIN.close()
                                logger.debug("Closing Camera Display Window")
                                pattern_view = False

                            # UnHide Home Screen
                            HOME_WIN.UnHide()
                            break
                            
                        # Controlling The Number Of Bbox Displayed
                        if (nms_cam_view_event == "-Update_Crop-") and (cam_view == True):
                            if Crop != "Disabled":
                                sg.popup("CROP CONTROL","Please Disable Crop To Use This Control",keep_on_top=True)

                            # Disable Multi-Bbox Window  
                            elif (int(nms_cam_view_values["-Bbox_Count-"]) <= 1):
                                Mode = "single"
                                Count_Reset = 1

                                # NMS Control Mode
                                c.execute(f"""UPDATE nmsctrl SET Mode = "{Mode}",Bbox_Count = "{Count_Reset}" WHERE rowid = 1""")

                                # Commit Update Tranx
                                conn.commit()

                                # NMS Control Database Connection
                                nmsctrl_data = database("nmsctrl")


                            # Enable Multi-Bbox Window
                            elif (int(nms_cam_view_values["-Bbox_Count-"]) > 1):
                                Mode = "multiple"
                                Multi_Crop = "Enabled"

                        if (Mode == "multiple") and (Multi_Crop == "Enabled") and (Window_Read == False):
                            
                            # Activate Control Window
                            NMS_BBOX_CONTROL_WIN, nms_bbox_ctrl_Width, nms_bbox_ctrl_Height = NMS_Bbox_Control_Win(Count = int(nms_cam_view_values["-Bbox_Count-"]))

                            # Activate Window Read
                            Window_Read = True
                            Multi_Sync = nmsctrl_data[10]
                            
                        if Window_Read == True:
                            # Deactivate On Screen Controls
                            Crop = "Disabled"
                            Sync = "Disabled"

                            # Active Crop Window
                            nms_bbox_ctrl_event,nms_bbox_ctrl_values = NMS_BBOX_CONTROL_WIN.read(timeout=5)

                            # Close Multi Bbox Control Window
                            if (nms_bbox_ctrl_event == sg.WIN_CLOSED):
                                Window_Read = False
                                Multi_Crop = "Disabled"
                                NMS_BBOX_CONTROL_WIN.close()

                            # Disable Multi_Sync
                            if (Multi_Crop == "Enabled") and (Multi_Sync == "Enabled") and (nms_bbox_ctrl_event == "-Disable_Multi_Sync-"):
                                NMS_BBOX_CONTROL_WIN["-Disable_Multi_Sync-"].Update(disabled=True)
                                NMS_BBOX_CONTROL_WIN["-Enable_Multi_Sync-"].Update(disabled=False)
                                for i in range(1,(value_range+1)):
                                    NMS_BBOX_CONTROL_WIN[f"-SYNC_BEGIN_X_{i}-"].Update(disabled=False)
                                    NMS_BBOX_CONTROL_WIN[f"-SYNC_BEGIN_Y_{i}-"].Update(disabled=False)
                                    NMS_BBOX_CONTROL_WIN[f"-SYNC_END_X_{i}-"].Update(disabled=False)
                                    NMS_BBOX_CONTROL_WIN[f"-SYNC_END_Y_{i}-"].Update(disabled=False)
                                Multi_Sync = "Disabled"
                            
                            # Enabled Multi_Sync
                            if (Multi_Crop == "Enabled") and (Multi_Sync == "Disabled") and (nms_bbox_ctrl_event == "-Enable_Multi_Sync-"):
                                NMS_BBOX_CONTROL_WIN["-Enable_Multi_Sync-"].Update(disabled=True)
                                NMS_BBOX_CONTROL_WIN["-Disable_Multi_Sync-"].Update(disabled=False)
                                for i in range(1,(value_range+1)):
                                    NMS_BBOX_CONTROL_WIN[f"-SYNC_BEGIN_X_{i}-"].Update(disabled=True)
                                    NMS_BBOX_CONTROL_WIN[f"-SYNC_BEGIN_Y_{i}-"].Update(disabled=True)
                                    NMS_BBOX_CONTROL_WIN[f"-SYNC_END_X_{i}-"].Update(disabled=True)
                                    NMS_BBOX_CONTROL_WIN[f"-SYNC_END_Y_{i}-"].Update(disabled=True)
                                Multi_Sync = "Enabled"
                            
                            # Display All Bbox
                            if (Multi_Crop == "Enabled"):
                                if Active_Stream == True:
                                    try:
                                        # Write Even To Capture Image Update Operations Window
                                        NMS_CAM_VIEW_WIN.write_event_value('TAKE PICTURE', "")
                                        Active_Stream = False
                                    except:
                                        sg.Popup('Please Take A Picture', keep_on_top=True)
                                        Multi_Crop = "Disabled"
                                        Multi_Sync = "Disabled"
                                        NMS_BBOX_CONTROL_WIN.close()

                                else:
                                    # Enables Synced OR Independent Inputs Depending on The MultiSync State
                                    if Multi_Sync == "Enabled":

                                        # Synced Input Condition 
                                        Check_List = ("-CROP")
                                    
                                    elif Multi_Sync == "Disabled":

                                        # Independent Input Condition
                                        Check_List = ("-CROP","-SYNC") 

                                    for value_key in nms_bbox_ctrl_values:
                                        if value_key.startswith(Check_List):
                                            
                                            # Enabled Input
                                            NMS_BBOX_CONTROL_WIN[value_key].Update(disabled=False)

                                        # Removing Empty Value Errors
                                        if nms_bbox_ctrl_values[value_key] == "":
                                            nms_bbox_ctrl_values.update({value_key : 0})
                                    
                                    # Try To Draw Bbox On The Display Image
                                    try:
                                        # Set Crop Boundary Values
                                        value_range = int(nms_cam_view_values["-Bbox_Count-"])

                                        # Loop Over The Bbox Count 
                                        for i in range(1,(value_range+1)):
                                            
                                            # Drawing Bounding Box On Image 
                                            try: 
                                                
                                                # Type Casting Values To Integers 
                                                CB_X = int(nms_bbox_ctrl_values[f"-CROP_BEGIN_X_{i}-"])
                                                CB_Y = int(nms_bbox_ctrl_values[f"-CROP_BEGIN_Y_{i}-"])
                                                CE_X = int(nms_bbox_ctrl_values[f"-CROP_END_X_{i}-"])
                                                CE_Y = int(nms_bbox_ctrl_values[f"-CROP_END_Y_{i}-"])

                                                # Sync The Position of the Bounding Boxes 
                                                if (Multi_Sync == "Enabled"):
                                                    
                                                    # AutoMatically Assign Image Bbox Positions To The Pattern Positions
                                                    try:
                                                        # Synched Bbox Parameters
                                                        SB_X = int(nms_bbox_ctrl_values[f"-CROP_BEGIN_X_{i}-"])
                                                        SB_Y = int(nms_bbox_ctrl_values[f"-CROP_BEGIN_Y_{i}-"])
                                                        SE_X = int(nms_bbox_ctrl_values[f"-CROP_END_X_{i}-"])
                                                        SE_Y = int(nms_bbox_ctrl_values[f"-CROP_END_Y_{i}-"])

                                                        # Setting Sync Values To Crop Values
                                                        NMS_BBOX_CONTROL_WIN[f"-SYNC_BEGIN_X_{i}-"].Update(int(nms_bbox_ctrl_values[f"-CROP_BEGIN_X_{i}-"]))
                                                        NMS_BBOX_CONTROL_WIN[f"-SYNC_BEGIN_Y_{i}-"].Update(int(nms_bbox_ctrl_values[f"-CROP_BEGIN_Y_{i}-"]))
                                                        NMS_BBOX_CONTROL_WIN[f"-SYNC_END_X_{i}-"].Update(int(nms_bbox_ctrl_values[f"-CROP_END_X_{i}-"]))
                                                        NMS_BBOX_CONTROL_WIN[f"-SYNC_END_Y_{i}-"].Update(int(nms_bbox_ctrl_values[f"-CROP_END_Y_{i}-"]))
                                                                                
                                                    except ValueError:
                                                        sg.Popup("INVALID INPUT","All Bbox Input Should Be Integers", keep_on_top=True)
                                                
                                                # If Sync of the Positions Of The Bounding Box Are Disabled
                                                elif (Multi_Sync == "Disabled"):
                                                    
                                                    # Assign Input Data To Variables
                                                    try:
                                                        # Unsynched Bbox boundary Values
                                                        SB_X = int(nms_bbox_ctrl_values[f"-SYNC_BEGIN_X_{i}-"])
                                                        SB_Y = int(nms_bbox_ctrl_values[f"-SYNC_BEGIN_Y_{i}-"])
                                                        SE_X = int(nms_bbox_ctrl_values[f"-SYNC_END_X_{i}-"])
                                                        SE_Y = int(nms_bbox_ctrl_values[f"-SYNC_END_Y_{i}-"])
                                                    
                                                    except ValueError:
                                                        sg.Popup("INVALID INPUT","All Bbox Input Should Be Integers", keep_on_top=True)
                                                
                                                # Image Bbox Parameters
                                                Bbox_start_point = (CB_X,CB_Y)
                                                Bbox_end_point = (CE_X,CE_Y)
                                                color = Bbox_Line_Color
                                                line_width = Bbox_Line_Width

                                                # Pattern Bbox Parameters
                                                Sync_start_point = (SB_X,SB_Y)
                                                Sync_end_point = (SE_X,SE_Y)
                                                color = Bbox_Line_Color
                                                line_width = Bbox_Line_Width

                                                # Draw Bbox On Image
                                                if i == 1:
                                                    frame_copy = copy.deepcopy(frame)
                                                new_Image = cv2.rectangle(frame_copy, Bbox_start_point, Bbox_end_point, color, line_width)
                                                cv2.putText(new_Image, f'{i}', (CB_X+5,CB_Y+25), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, line_width)
                                                Image_resized = cv2.resize(new_Image, (nms_cam_Width, nms_cam_Height), interpolation=cv2.INTER_AREA)
                                                cropbytes = cv2.imencode('.png', Image_resized)[1].tobytes()
                                                NMS_CAM_VIEW_WIN['camera'].update(data=cropbytes)

                                                # Bbox Image To Section
                                                Pattern_Image = cv2.imread(Pattern_File_Path)
                                                if i == 1:
                                                    Pattern_Image_Copy = copy.deepcopy(Pattern_Image)
                                                Bbox_Pattern_Image_Copy = cv2.rectangle(Pattern_Image_Copy, Sync_start_point, Sync_end_point, color, line_width)
                                                cv2.putText(Bbox_Pattern_Image_Copy, f'{i}', (SB_X+5,SB_Y+25), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, line_width)
                                                Resized_Bbox_Pattern_Image_Copy = cv2.resize(Bbox_Pattern_Image_Copy, (nms_pattern_Width, nms_pattern_Height), interpolation=cv2.INTER_AREA)
                                                Bbox_Current_Pattern_Copy_imgbytes = cv2.imencode('.png', Resized_Bbox_Pattern_Image_Copy)[1].tobytes()
                                                NMS_PATTERN_VIEW_WIN['Pattern_Display'].update(data=Bbox_Current_Pattern_Copy_imgbytes)
                                            
                                            except ValueError:
                                                sg.Popup("INVALID INPUT","All Bbox Input Should Be Integers", keep_on_top=True)           
                                    
                                    except Exception as e:
                                        logger.exception(str(e))
                            
                            # Sample SSIM Test
                            if (nms_bbox_ctrl_event != None) and (nms_bbox_ctrl_event.startswith("-Ssim_Test_")):
                                Button_Key = nms_bbox_ctrl_event
                                Button_Key = Button_Key.split("-")[1]
                                Key_Split = Button_Key.split("_")
                                Section_Id = Key_Split[-1]
                                
                                # FETCH FRAME IMAGE
                                CB_X = int(nms_bbox_ctrl_values[f"-CROP_BEGIN_X_{Section_Id}-"])
                                CB_Y = int(nms_bbox_ctrl_values[f"-CROP_BEGIN_Y_{Section_Id}-"])
                                CE_X = int(nms_bbox_ctrl_values[f"-CROP_END_X_{Section_Id}-"])
                                CE_Y = int(nms_bbox_ctrl_values[f"-CROP_END_Y_{Section_Id}-"])

                                # FETCH PATTERN BBOX
                                SB_X = int(nms_bbox_ctrl_values[f"-SYNC_BEGIN_X_{Section_Id}-"])
                                SB_Y = int(nms_bbox_ctrl_values[f"-SYNC_BEGIN_Y_{Section_Id}-"])
                                SE_X = int(nms_bbox_ctrl_values[f"-SYNC_END_X_{Section_Id}-"])
                                SE_Y = int(nms_bbox_ctrl_values[f"-SYNC_END_Y_{Section_Id}-"])

                                Camera_Cropped_Section = frame[CB_Y:CE_Y, CB_X:CE_X]
                                try:
                                    Pattern_Cropped_Section = Pattern_Image_Copy[SB_Y:SE_Y, SB_X:SE_X]

                                    if (Camera_Cropped_Section.shape != Pattern_Cropped_Section.shape):
                                        sg.Popup('Please Ensure Camera Image and Pattern Image Are The Same Size', keep_on_top=True)
                                    
                                    else:
                                        (Result, diff) = compare_ssim(Camera_Cropped_Section, Pattern_Cropped_Section, full=True, multichannel=True)
                                        logger.debug("Carried out Sample SSIM Test")
                                        logger.debug(f"Test Result for Bbox_{Section_Id} is {Result}")
                                        NMS_BBOX_CONTROL_WIN[f"S_ssim_{Section_Id}"].Update(round(Result,6))
                                except:
                                    sg.popup("NO Pattern Image Selected, Please Selecte A Pattern Image", title = "SSIM TEST", keep_on_top=True)

                            # Save Data
                            if (nms_bbox_ctrl_event == "-SAVE_Multi_Crop-"):
                                
                                # Get All Bbox Cordinates:
                                value_range = int(nms_cam_view_values["-Bbox_Count-"])  
                                
                                # Bbox Data Collector
                                Multi_Crop_Data = dict()  
                                
                                # Loop Over The Input Fields And Colect Their Values
                                for i in range(1,(value_range+1)):
                                    
                                    # Drawing Bounding Box On Image 
                                    try: 
                                        
                                        # Collect Image Bbox Coordinates 
                                        Multi_Crop_Data[f"CB_X_Bbox_{i}"] = int(nms_bbox_ctrl_values[f"-CROP_BEGIN_X_{i}-"])
                                        Multi_Crop_Data[f"CB_Y_Bbox_{i}"] = int(nms_bbox_ctrl_values[f"-CROP_BEGIN_Y_{i}-"])
                                        Multi_Crop_Data[f"CE_X_Bbox_{i}"] = int(nms_bbox_ctrl_values[f"-CROP_END_X_{i}-"])
                                        Multi_Crop_Data[f"CE_Y_Bbox_{i}"] = int(nms_bbox_ctrl_values[f"-CROP_END_Y_{i}-"])

                                        # Collect Pattern Bbox Coordinates
                                        Multi_Crop_Data[f"SB_X_Bbox_{i}"] = int(nms_bbox_ctrl_values[f"-SYNC_BEGIN_X_{i}-"])
                                        Multi_Crop_Data[f"SB_Y_Bbox_{i}"] = int(nms_bbox_ctrl_values[f"-SYNC_BEGIN_Y_{i}-"])
                                        Multi_Crop_Data[f"SE_X_Bbox_{i}"] = int(nms_bbox_ctrl_values[f"-SYNC_END_X_{i}-"])
                                        Multi_Crop_Data[f"SE_Y_Bbox_{i}"] = int(nms_bbox_ctrl_values[f"-SYNC_END_Y_{i}-"])
                                    
                                    except Exception as e:
                                        print(f"Unable To Create Data Dict {e}")
                                
                                # NMS Control Mode
                                c.execute(f"""
                                UPDATE nmsctrl 
                                SET Mode = "{Mode}", Multi_Sync = "{Multi_Sync}", Multi_Crop = "{Multi_Crop}",Bbox_Count = "{int(nms_cam_view_values["-Bbox_Count-"])}",Bbox_Data = "{str(Multi_Crop_Data)}"
                                WHERE rowid = 1""")

                                # Commit Update Tranx
                                conn.commit()

                                # NMS Control Database Connection
                                nmsctrl_data = database("nmsctrl")

                                # Notification Window
                                sg.popup("Your Data Has Been Saved", title="NOTIFICATION WINDOW", keep_on_top=True)

                        # Switch To Turn On and Off Crop Display
                        if (nms_cam_view_event == "-Enable Crop-") and (cam_view == True):
                            Crop = "Enabled"
                        
                        # Image Crop Utility
                        if (Crop == "Enabled"):

                            if Active_Stream == True:
                                sg.Popup('Please Take A Picture', keep_on_top=True)
                                Crop = "Disabled"

                            else:
                                NMS_CAM_VIEW_WIN["-Enable Crop-"].Update(disabled=True)
                                NMS_CAM_VIEW_WIN["-Disable Crop-"].Update(disabled=False)
                                NMS_CAM_VIEW_WIN["-CROP_BEGIN_X-"].Update(disabled=False)
                                NMS_CAM_VIEW_WIN["-CROP_BEGIN_Y-"].Update(disabled=False)
                                NMS_CAM_VIEW_WIN["-CROP_END_X-"].Update(disabled=False)
                                NMS_CAM_VIEW_WIN["-CROP_END_Y-"].Update(disabled=False)
                                    
                                # Removing Empty Value Errors
                                if nms_cam_view_values["-CROP_BEGIN_X-"] == "":
                                    nms_cam_view_values.update({"-CROP_BEGIN_X-" : 0})

                                if nms_cam_view_values["-CROP_BEGIN_Y-"] == "":
                                    nms_cam_view_values.update({"-CROP_BEGIN_Y-" : 0})
                                
                                if nms_cam_view_values["-CROP_END_X-"] == "":
                                    nms_cam_view_values.update({"-CROP_END_X-" : 0})

                                if nms_cam_view_values["-CROP_END_Y-"] == "":
                                    nms_cam_view_values.update({"-CROP_END_Y-" : 0})
                            
                                # Set Crop Boundary Values
                                try:    
                                    CB_X = int(nms_cam_view_values["-CROP_BEGIN_X-"])
                                    CB_Y = int(nms_cam_view_values["-CROP_BEGIN_Y-"])
                                    CE_X = int(nms_cam_view_values["-CROP_END_X-"])
                                    CE_Y = int(nms_cam_view_values["-CROP_END_Y-"])
                                
                                except ValueError:
                                    sg.Popup("INVALID INPUT","All Bbox Input Should Be Integers", keep_on_top=True)

                                # Bbox Parameters
                                Bbox_start_point = (CB_X,CB_Y)
                                Bbox_end_point = (CE_X,CE_Y)
                                color = Bbox_Line_Color
                                line_width = Bbox_Line_Width
                                
                                # Crop To Section
                                frame_copy = copy.deepcopy(frame)
                                new_Image = cv2.rectangle(frame_copy, Bbox_start_point, Bbox_end_point, color, line_width)
                                Image_resized = cv2.resize(new_Image, (nms_cam_Width, nms_cam_Height), interpolation=cv2.INTER_AREA)
                                cropbytes = cv2.imencode('.png', Image_resized)[1].tobytes()
                                NMS_CAM_VIEW_WIN['camera'].update(data=cropbytes)

                        if (nms_cam_view_event == "-Disable Crop-") and (cam_view == True):
                            NMS_CAM_VIEW_WIN["-Enable Crop-"].Update(disabled=False)
                            NMS_CAM_VIEW_WIN["-Disable Crop-"].Update(disabled=True)
                            NMS_CAM_VIEW_WIN["-CROP_BEGIN_X-"].Update(disabled=True)
                            NMS_CAM_VIEW_WIN["-CROP_BEGIN_Y-"].Update(disabled=True)
                            NMS_CAM_VIEW_WIN["-CROP_END_X-"].Update(disabled=True)
                            NMS_CAM_VIEW_WIN["-CROP_END_Y-"].Update(disabled=True)
                            Crop = "Disabled"

                            # Clean Up Bbox Display
                            Clean_Frame = cv2.resize(frame, (nms_cam_Width, nms_cam_Height), interpolation=cv2.INTER_AREA)
                            cleanbytes = cv2.imencode('.png', Clean_Frame)[1].tobytes()
                            NMS_CAM_VIEW_WIN["camera"].Update(data=cleanbytes)
                            logger.debug("Cleaned Image Restored")

                        # Switches To Turn On and Off Bbox Sync
                        if (nms_cam_view_event == "-Enable Sync-") and (cam_view == True):
                            Sync = "Enabled"

                        if(Sync == "Enabled"):
                            NMS_CAM_VIEW_WIN["-Disable Sync-"].Update(disabled=False)
                            NMS_CAM_VIEW_WIN["-Enable Sync-"].Update(disabled=True)
                            NMS_CAM_VIEW_WIN["-SYNC_BEGIN_X-"].Update(disabled=True)
                            NMS_CAM_VIEW_WIN["-SYNC_BEGIN_Y-"].Update(disabled=True)
                            NMS_CAM_VIEW_WIN["-SYNC_END_X-"].Update(disabled=True)
                            NMS_CAM_VIEW_WIN["-SYNC_END_Y-"].Update(disabled=True)

                            # Setting Sync Values To Crop Values
                            NMS_CAM_VIEW_WIN["-SYNC_BEGIN_X-"].Update(int(nms_cam_view_values["-CROP_BEGIN_X-"]))
                            NMS_CAM_VIEW_WIN["-SYNC_BEGIN_Y-"].Update(int(nms_cam_view_values["-CROP_BEGIN_Y-"]))
                            NMS_CAM_VIEW_WIN["-SYNC_END_X-"].Update(int(nms_cam_view_values["-CROP_END_X-"]))
                            NMS_CAM_VIEW_WIN["-SYNC_END_Y-"].Update(int(nms_cam_view_values["-CROP_END_Y-"]))

                        if (nms_cam_view_event == "-Disable Sync-") and (cam_view == True):
                            Sync = "Disabled"

                        if (Sync == "Disabled"):
                            NMS_CAM_VIEW_WIN["-Disable Sync-"].Update(disabled=True)
                            NMS_CAM_VIEW_WIN["-Enable Sync-"].Update(disabled=False)
                            NMS_CAM_VIEW_WIN["-SYNC_BEGIN_X-"].Update(disabled=False)
                            NMS_CAM_VIEW_WIN["-SYNC_BEGIN_Y-"].Update(disabled=False)
                            NMS_CAM_VIEW_WIN["-SYNC_END_X-"].Update(disabled=False)
                            NMS_CAM_VIEW_WIN["-SYNC_END_Y-"].Update(disabled=False)

                            # Removing Empty Value Errors
                            if nms_cam_view_values["-SYNC_BEGIN_X-"] == "":
                                nms_cam_view_values.update({"-SYNC_BEGIN_X-" : 0})


                            if nms_cam_view_values["-SYNC_BEGIN_Y-"] == "":
                                nms_cam_view_values.update({"-SYNC_BEGIN_Y-" : 0})

                            
                            if nms_cam_view_values["-SYNC_END_X-"] == "":
                                nms_cam_view_values.update({"-SYNC_END_X-" : 0})

                            if nms_cam_view_values["-SYNC_END_Y-"] == "":
                                nms_cam_view_values.update({"-SYNC_END_Y-" : 0})


                        # If Pattern Window Is Open
                        if pattern_view == True:
                            nms_pattern_view_event, nms_pattern_view_values = NMS_PATTERN_VIEW_WIN.read(timeout=10)

                            # Change Displayed Pattern
                            if (nms_pattern_view_event != sg.WIN_CLOSED) and (nms_pattern_view_event != "__TIMEOUT__"):
                                
                                # Folder Paths
                                Pattern_File_Path = f"{NMS_Master_Pattern_Folder}/{nms_pattern_view_event}"
                                Thumbnail_File_Path= f"{NMS_Master_Thumbnails_Folder}/{nms_pattern_view_event}"

                                # Display Pattern Image
                                try:
                                    Thumbnails_Refresh(NMS_PATTERN_VIEW_WIN, nms_pattern_Width, nms_pattern_Height, nms_pattern_view_event, Pattern_File_Path, Thumbnail_File_Path, Image_List = os.listdir(NMS_Master_Thumbnails_Folder))
                                
                                except Exception as e:
                                    sg.Popup(f"File Does Not Exist {e}", keep_on_top=True)
                                    logger.exception(str(e))

                            # Closing Pattern Window
                            if(nms_pattern_view_event == sg.WIN_CLOSED):
                                NMS_PATTERN_VIEW_WIN.close()
                                pattern_view = False
                                logger.debug("Closed Pattern Window Only")

                            # Image Crop Utility
                            if (nms_cam_view_event == "-Enable Crop-") and (Active_Stream == False):
                                Align_Crop_Dimensions = True
                                logger.debug("Detected Crop is Enabled")
                            
                            if Align_Crop_Dimensions == True:
                                if (Sync == "Enabled"):
                                    try:
                                        # Synched Bbox Parameters
                                        SB_X = int(nms_cam_view_values["-CROP_BEGIN_X-"])
                                        SB_Y = int(nms_cam_view_values["-CROP_BEGIN_Y-"])
                                        SE_X = int(nms_cam_view_values["-CROP_END_X-"])
                                        SE_Y = int(nms_cam_view_values["-CROP_END_Y-"])
                                    
                                    except ValueError:
                                        sg.Popup("INVALID INPUT","All Bbox Input Should Be Integers", keep_on_top=True)
                                
                                elif (Sync == "Disabled"):
                                    try:
                                        # Unsynched Bbox boundary Values
                                        SB_X = int(nms_cam_view_values["-SYNC_BEGIN_X-"])
                                        SB_Y = int(nms_cam_view_values["-SYNC_BEGIN_Y-"])
                                        SE_X = int(nms_cam_view_values["-SYNC_END_X-"])
                                        SE_Y = int(nms_cam_view_values["-SYNC_END_Y-"])
                                    
                                    except ValueError:
                                        sg.Popup("INVALID INPUT","All Bbox Input Should Be Integers", keep_on_top=True)

                                # Bbox Parameters
                                Sync_start_point = (SB_X,SB_Y)
                                Sync_end_point = (SE_X,SE_Y)
                                color = Bbox_Line_Color
                                line_width = Bbox_Line_Width

                                # Bbox Image To Section
                                Pattern_Image = cv2.imread(Pattern_File_Path)
                                Pattern_Image_Copy = copy.deepcopy(Pattern_Image)
                                Bbox_Pattern_Image_Copy = cv2.rectangle(Pattern_Image_Copy, Sync_start_point, Sync_end_point, color, line_width)
                                Resized_Bbox_Pattern_Image_Copy = cv2.resize(Bbox_Pattern_Image_Copy, (nms_pattern_Width, nms_pattern_Height), interpolation=cv2.INTER_AREA)
                                Bbox_Current_Pattern_Copy_imgbytes = cv2.imencode('.png', Resized_Bbox_Pattern_Image_Copy)[1].tobytes()
                                NMS_PATTERN_VIEW_WIN['Pattern_Display'].update(data=Bbox_Current_Pattern_Copy_imgbytes)

                            if (nms_cam_view_event == "-Disable Crop-"):
                                Plain_Pattern_Image_resized = cv2.resize(Pattern_Image, (nms_pattern_Width, nms_pattern_Height), interpolation=cv2.INTER_AREA)
                                Plain_Pattern_Image_imgbytes = cv2.imencode('.png', Plain_Pattern_Image_resized)[1].tobytes()
                                NMS_PATTERN_VIEW_WIN['Pattern_Display'].update(data=Plain_Pattern_Image_imgbytes)
                                Align_Crop_Dimensions = False

                        # Single Bbox SSIM Test
                        if nms_cam_view_event == "-Ssim Test-":
                            if Active_Stream == True:
                                sg.Popup('Please Take A Picture', keep_on_top=True)

                            if Crop == "Disabled":
                                sg.Popup('Please Used The Cropping Tools To Define Region Of Focus', keep_on_top=True)
                                
                            if (Active_Stream == False) and (Crop == "Enabled"):
                                Camera_Cropped_Section = frame[CB_Y:CE_Y, CB_X:CE_X]
                                try:
                                    Pattern_Cropped_Section = Pattern_Image_Copy[SB_Y:SE_Y, SB_X:SE_X]

                                    if (Camera_Cropped_Section.shape != Pattern_Cropped_Section.shape):
                                        sg.Popup('Please Ensure Camera Image and Pattern Image Are The Same Size', keep_on_top=True)
                                    
                                    else:
                                        (Result, diff) = compare_ssim(Camera_Cropped_Section, Pattern_Cropped_Section, full=True, multichannel=True)
                                        logger.debug("Carried out Sample SSIM Test")
                                        logger.debug(f"Test Result is {Result}")
                                        NMS_CAM_VIEW_WIN["S_ssim"].Update(round(Result,6))

                                        # Diffrence On Every Pixel
                                        # diff = (diff * 255).astype("uint8")
                                except:
                                    sg.popup("NO Pattern Image Selected, Please Selecte A Pattern Image", title = "SSIM TEST", keep_on_top=True)
                        
                        # Adding An NMS File
                        if nms_cam_view_event == "-Add-":

                            # Capture Image From Live Feed
                            ret, frame = cap.read()
                            Id_Count = len(os.listdir(NMS_Master_Pattern_Folder)) + 1
                            
                            # Write New Sample To Sample Folder
                            cv2.imwrite(f"{NMS_Master_Pattern_Folder}/{Id_Count}_Pattern.png", frame)
                            sg.Popup('Pattern Saved', f'New Pattern Saved As {Id_Count}_Pattern.png', keep_on_top=True)
                            Thumbnails()
                            
                            # Close Old Window
                            NMS_PATTERN_VIEW_WIN.close()
                            pattern_view = False
                            logger.debug("Closing Old Pattern Window")

                            #  Open New Window
                            NMS_PATTERN_VIEW_WIN, nms_pattern_Width, nms_pattern_Height = NMS_Pattern_View()
                            pattern_view = True
                            logger.debug("Opening New Pattern View")
                            
                            # Focus File
                            Pattern_File_Path = f"{NMS_Master_Pattern_Folder}/{Id_Count}_Pattern.png"
                            Thumbnail_File_Path= f"{NMS_Master_Thumbnails_Folder}/{Id_Count}_Pattern.png"

                            # Refresh Thumbnails
                            Thumbnails_Refresh(NMS_PATTERN_VIEW_WIN, nms_pattern_Width, nms_pattern_Height, f"{Id_Count}_Pattern.png", Pattern_File_Path, Thumbnail_File_Path, Image_List = os.listdir(NMS_Master_Thumbnails_Folder))

                        # Replacing An NMS File
                        if nms_cam_view_event == "-Replace-":

                            # Obtain Current Sample Name
                            if Pattern_File_Path.lower().endswith(".png"):
                            
                                # Write New Sample Image To Sample Directory
                                ret, frame = cap.read()
                                NMS = cv2.imwrite(f"{Pattern_File_Path}", frame)
                                
                                # Create Thumbnail
                                New_NMS_img = cv2.imread(f"{Pattern_File_Path}")
                                resized_img = cv2.resize(New_NMS_img, (150, 150), interpolation=cv2.INTER_AREA)

                                # Create Thumbnail Path
                                Image_Path = Pattern_File_Path.split("/")
                                Image_Name = Image_Path[-1]

                                # Save Thumbnail
                                cv2.imwrite(f"{NMS_Master_Thumbnails_Folder}/{Image_Name}",resized_img)
                                Thumbnails_Refresh(NMS_PATTERN_VIEW_WIN, nms_pattern_Width, nms_pattern_Height, Image_Name, Pattern_File_Path, Thumbnail_File_Path, Image_List = os.listdir(NMS_Master_Thumbnails_Folder))

                            else:
                                sg.Popup("The Selected File Is Invalid", keep_on_top=True)

                        # Remove An NMS File
                        if nms_cam_view_event == "-Remove-":

                            try:    
                                # Remove Pattern Image and Thumbnails
                                os.remove(f"{Pattern_File_Path}")
                                os.remove(f"{Thumbnail_File_Path}")
                                logger.debug("Delete Complete")

                            except Exception as e:
                                logger.exception(f"File Already Deleted {str(e)}")
                                sg.Popup("File Already Deleted", keep_on_top=True)

                            else:
                                try:
                                    # Close Old Window
                                    NMS_PATTERN_VIEW_WIN.close()
                                    pattern_view = False
                                    logger.debug("Closing Old Pattern Window")
                                
                                except Exception as e:
                                   logger.exception(f"Error While Closing Old Pattern Window {str(e)}")
                                   sg.Popup("Error While Closing Old Pattern Window", keep_on_top=True)

                                else:
                                    try:
                                        # Refresh Default Display Pattern
                                        Default_Pattern = f"{NMS_Master_Pattern_Folder}/{os.listdir(NMS_Master_Thumbnails_Folder)[0]}"

                                        # Open New Window
                                        NMS_PATTERN_VIEW_WIN, nms_pattern_Width, nms_pattern_Height = NMS_Pattern_View(Default_Pattern = Default_Pattern)
                                        pattern_view = True
                                        logger.debug("Opening New Pattern View")

                                        # Refresh Thumbnails
                                        Thumbnails_Refresh(NMS_PATTERN_VIEW_WIN, nms_pattern_Width, nms_pattern_Height, None, Pattern_File_Path, Thumbnail_File_Path, Image_List = os.listdir(NMS_Master_Thumbnails_Folder))

                                    except Exception as e:
                                        logger.exception(f"Unable To Launch New Window {str(e)}")
                                        sg.Popup(f"Unable To Reset Window After Deletinfg File", keep_on_top=True)

                        # Saving NMS Data
                        if nms_cam_view_event == "SAVE":
                            
                            # NMS Control Parameters
                            c.execute(f"""UPDATE nmsctrl
                                        SET Sync_Status = "{Sync}", Crop_X1 = {nms_cam_view_values["-CROP_BEGIN_X-"]}, Crop_X2 = {nms_cam_view_values["-CROP_END_X-"]}, Crop_Y1 = {nms_cam_view_values["-CROP_BEGIN_Y-"]}, Crop_Y2 = {nms_cam_view_values["-CROP_END_Y-"]},
                                        Sync_X1 = {nms_cam_view_values["-SYNC_BEGIN_X-"]}, Sync_X2 = {nms_cam_view_values["-SYNC_END_X-"]}, Sync_Y1 = {nms_cam_view_values["-SYNC_BEGIN_Y-"]}, Sync_Y2 = {nms_cam_view_values["-SYNC_END_Y-"]}
                                        WHERE rowid = 1""")

                            # Commit Update Tranx
                            conn.commit()

                            # NMS Control Database Connection
                            nms_data = database("nmsctrl")

                else:
                    sg.Popup("Please Select An Available Camera", keep_on_top=True)           
            
            # Batch Creation Of NMS
            if home_event == "Collect Batch Data":
                
                # Check Camera Availability
                if Cam_Test(Camera_Index = Selected_Camera) == True:
                    
                    # Hiding Home Window
                    HOME_WIN.Hide()

                    # set Batch Window To Active
                    closed = False
                    Source_Start = False
                    Batch_Active = True
                    Batch_Stream = True
                    Batch_Collect = False
                    Batch_Pattern_Count = 000

                    # Fetch Data From Setting Database
                    """ Connect To DB """
                    othset_data = database("othsetctrl")
                    
                    """ Fetch Data From DB """
                    BATCH_Pattern_Folder = f"{othset_data[6]}"
                    
                    # Count_Down Timer
                    Count_Down_Timer = othset_data[0]

                    # NMS Camera Window
                    BATCH_CAPTURE_WIN, bc_Width, bc_Height = Batch_Capture()
                    logger.debug("Opening Batch Capture Window")

                    # Start Camera
                    BC_cap = cv2.VideoCapture(Selected_Camera, cv2.CAP_DSHOW)

                    # Camera Focus Control
                    BC_cap.set(cv2.CAP_PROP_FOCUS, Current_Focus_Val)

                    while Batch_Active:
                        bc_event,bc_values = BATCH_CAPTURE_WIN.read(timeout=10)

                        try:
                            # Read Batch Capture Pattern Window
                            if bcp_view == True:
                                bcp_event,bcp_values = BCP_WIN.read(timeout=10)
                            
                            # Close Batch Caprure Pattern Window
                            if (bcp_view == True) and (bcp_event == sg.WIN_CLOSED):
                                bcp_view = False
                                BCP_WIN.close()
                                logger.debug("Closed Batch Capture Pattern Window")
                                bcp_event = None
                            
                        except:
                            pass

                        # On Start Stream Video From Camera
                        if (Batch_Stream == True):
                            ret, frame = BC_cap.read()
                            live_feed_resized = cv2.resize(frame, (250, 200), interpolation=cv2.INTER_AREA)
                            imgbytes = cv2.imencode('.png', live_feed_resized)[1].tobytes()
                            BATCH_CAPTURE_WIN['-BC_Camera_Display-'].update(data=imgbytes)


                        # Taking Pictures
                        if (bc_event == "START") and (Batch_Active == True):

                            if (bc_values["Selected_Folder_Path"] != "No Folder Selected") and (bc_values["Selected_Folder_Path"] != ""):

                                # Relative Path Of Source Folder
                                Pattern_Origin_Folder = os.path.relpath(bc_values["Selected_Folder_Path"])
                                Pattern_Origin_Folder = Pattern_Origin_Folder.replace("\\","/")

                                # Folder Selection Check
                                Source_Start = True

                                # Properly Named Images In Source Folder
                                Origin_Folder_Proper_Names = [x for x in os.listdir(Pattern_Origin_Folder) if x.endswith("Pattern.png")]
                                
                                # Modify_Source_Folder
                                Patterns_To_Rename = [x for x in os.listdir(Pattern_Origin_Folder) if x not in Origin_Folder_Proper_Names]

                                # Creating Thumbnails
                                if Patterns_To_Rename != []:
                                    logger.debug("Origin Pattern Files")

                                    # Get Number Of Properly Named Files
                                    Pattern_Number = len(Origin_Folder_Proper_Names)

                                    BAR_MAX = len(Patterns_To_Rename)

                                    # layout the Window
                                    layout = [[sg.Text('Renaming Patterns In Folder, \nCanceling May Lead To Duplication Of Data')],
                                            [sg.ProgressBar(BAR_MAX, orientation='h', size=(35,10), key='-PROG-')]]

                                    # create the Window
                                    pmwindow = sg.Window('Progress Meter', layout, keep_on_top=True, finalize=True)

                                    # Create Properly Named Images
                                    for i,img in enumerate(tqdm(Patterns_To_Rename, desc = "Creating Origin Files")):
                                        
                                        pmevent, pvalues = pmwindow.read(timeout=10)

                                        # Check For Window Close
                                        if pmevent == sg.WIN_CLOSED:
                                            closed = True
                                            break
                                        else:
                                            closed = False

                                        Current_img = cv2.imread(f"{Pattern_Origin_Folder}/{img}")
                                        Pattern_Number = int(Pattern_Number)
                                        Pattern_Number += 1
                                        if len(str(Pattern_Number)) < 2:
                                            Pattern_Number = f"0{Pattern_Number}"
                                        try:
                                            Errored = False
                                            cv2.imwrite(f"{Pattern_Origin_Folder}/{Pattern_Number}_Pattern.png",Current_img)
                                        
                                        except Exception as e:
                                            bcp_view = False
                                            Errored = True
                                            sg.Popup("Selected Folder Does Not Contain Images, Please Select Another.", title="Folder Error", keep_on_top=True)

                                        # Update Progress Bar
                                        pmwindow['-PROG-'].update(i+1)

                                    # done with loop... need to destroy the window as it's still open
                                    pmwindow.close()

                                    logger.debug("Renamed All Pattern Files")
                                    
                                    if closed == False:    
                                        # Remove Improperly Named Images
                                        logger.debug("Cleaning Up Pattern Folder")
                                        
                                        if Errored != True:
                                            for File in tqdm(Patterns_To_Rename, desc = "Cleaning Origin Folder"):
                                                os.remove(f"{Pattern_Origin_Folder}/{File}")
                                        
                                        logger.debug("Pattern Folder Cleaned")
                                
                                # Check If The Pattern Creation Tab Was Not Closed
                                if closed == False:

                                    ######################
                                    ## PATTERN WINDOW
                                    ######################

                                    # Select Thumbnail File To be highlighted
                                    Pattern_Files = os.listdir(Pattern_Origin_Folder)
                                    Pattern_Files.sort(key=natural_keys)
                                    Current_Count = 0

                                    # Refresh Default Display Pattern
                                    Default_Pattern = f"{Pattern_Origin_Folder}/{Pattern_Files[Current_Count]}"

                                    # Activate Pattern View Window
                                    try:
                                        BCP_WIN, BCP_Width, BCP_Height = Batch_Capture_Pattern(Default_Pattern = Default_Pattern)
                                        bcp_view = True

                                        # Create New Pattern Folder Or Add To Existing Folder
                                        Response = sg.popup_yes_no("Would You Like To Create A New Patten Folder For These Patterns.\nIf you select 'NO', the collected patterns will be added to the current pattern folder in use", title = "Create Folder",keep_on_top=True)

                                        if Response == "Yes":
                                            Folder_Name = sg.popup_get_text("Enter Folder Name", title = "Folder Name",keep_on_top=True)
                                            Parent_Folder = os.path.dirname(Pattern_Origin_Folder)

                                            try: 
                                                os.makedirs(f"{Parent_Folder}/{Folder_Name}")
                                                logger.debug(f"Created New Pattern Folder at {Parent_Folder}/{Folder_Name}")
                                                BATCH_Pattern_Folder = f"{Parent_Folder}/{Folder_Name}"
                                            
                                            except Exception as e:
                                                sg.popup(f"An Error Occured While Creating Your Folder {e}","Unable To Create Folder",keep_on_top=True)
                                                BCP_WIN.close()
                                                bcp_view = False

                                        # Count Number of PatternS Currently In Pattern Folder
                                        Batch_Pattern_Count = len(os.listdir(BATCH_Pattern_Folder))
                                        BATCH_CAPTURE_WIN["-Counter-"].update(Batch_Pattern_Count)

                                        logger.debug("Starting Camera Stream")
                                        Batch_Collect = True


                                    except TypeError:
                                        sg.popup("Plase Select A Valid Folder", title="Invalid Folder", keep_on_top = True)
                                else:
                                    bcp_view = False
                                    sg.popup("Pattern Creation Process Closed, Kindly Try Again", title="WARNING", keep_on_top=True)
                            else:
                                bcp_view = False
                                sg.popup("No Folder Selected, Please Select A Folder", title = "No Folder Selected", keep_on_top=True)

                        
                            # Notify User To Restart The Batch Capture System on Error
                            if (bcp_view == False) and (Batch_Collect == True):
                                Batch_Collect = False
                                sg.popup("Please Restart Batch Capture and Create A Folder With A Unique Name", title="BATCH FOLDER ERROR", keep_on_top=True)
                        
                        #  Start Batch Picture Taking With Count Down
                        if (Batch_Collect == True) and (len(All_Threads) == 0):

                            # Create Countdown Threads
                            if len(All_Threads) == 0:
                                Exit_Thread.clear()  
                                All_Threads.append(threading.Thread(target=countdown, args=(BATCH_CAPTURE_WIN, Count_Down_Timer), daemon=True).start())
                                    
                        # Updating Count Down On Display
                        if bc_event == "-THREAD_TIMER-":
                            BATCH_CAPTURE_WIN['-Timer-'].update(bc_values["-THREAD_TIMER-"])

                        # Activate Image Capture and Save Image To Patten Folder
                        if (bc_event == "-SSIM_ACTIVATE-"):

                            if bcp_view == False:
                                sg.popup("Pattern Window is Closed Please Restart Batch Capture",title = "Closed Pattern Window", keep_on_top=True)
                            
                            else:
                                # Capture Image
                                logger.debug('Capturing Pattern Image')
                                ret, frame = BC_cap.read()
                                resized_capture = cv2.resize(frame, (bc_Width, bc_Height), interpolation=cv2.INTER_AREA)
                                camera_capturebytes = cv2.imencode('.png',resized_capture)[1].tobytes()

                                # Update Pattern Count Widget
                                Batch_Pattern_Count = Batch_Pattern_Count + 1
                                BATCH_CAPTURE_WIN["-Counter-"].update(Batch_Pattern_Count)
                                
                                # Show Image
                                BATCH_CAPTURE_WIN['-BC_Image_Capture-'].update(data=camera_capturebytes)

                                # Clear Tracking Thread
                                All_Threads.clear()
                                
                                # Adding The "0" Prefix
                                if Batch_Pattern_Count <= 9:
                                    Batch_Pattern_Count = f"0{Batch_Pattern_Count}"

                                # Save Pattern Image
                                cv2.imwrite(f"{BATCH_Pattern_Folder}/{Batch_Pattern_Count}_Pattern.png", frame)

                                # Type Cast Back To Integer
                                Batch_Pattern_Count = int(Batch_Pattern_Count)

                                # Update Displayed Pattern)
                                Current_Count += 1
                                ReadImage = cv2.imread(f"{Pattern_Origin_Folder}/{Pattern_Files[Current_Count]}")
                                Read_Resize = cv2.resize(ReadImage, (BCP_Width, BCP_Height), interpolation=cv2.INTER_AREA)
                                ReadImage_Bytes = cv2.imencode('.png', Read_Resize)[1].tobytes()
                                BCP_WIN["Pattern_Display"].update(data = ReadImage_Bytes)

                        # Start Stream
                        if (bc_event == "STOP") and (Source_Start == True):
                            Exit_Thread.set()
                            All_Threads.clear()
                            Source_Start = False
                            Batch_Collect = False
                            logger.debug("Stopping Batch Capture System")
                            
                            # Update The New Mirror Standard
                            Change_NMS = sg.popup_yes_no("Would You Like To Update To A New Mirror Standard Folder",title="Update Mirror Standard", keep_on_top=True)

                            # Chnage NMS Folder
                            if Change_NMS == "Yes":

                                # layout the Window
                                SFlayout = [[sg.Text('Select Folder')],
                                        [
                                            sg.InputText("No Folder Selected", font=("Courier 10",10), enable_events=True, size = (18,1), justification = "left", key="-Selected_Folder_Path-"),
                                            sg.FolderBrowse()
                                        ],
                                        [sg.Button("Close", button_color=("white","red")), sg.Button("Save", key="-Save_Folder-")]]

                                # create the Window
                                SFwindow = sg.Window('Pattern Folder Explorer', SFlayout, finalize=True, keep_on_top=True)

                                # loop that would normally do something useful
                                while True:

                                    # check to see if the cancel button was clicked and exit loop if clicked
                                    SFevent, SFvalues = SFwindow.read(timeout=10)
                                    
                                    # Close Window
                                    if SFevent == 'Close' or SFevent == sg.WIN_CLOSED:
                                        break

                                    # Save New Folder Location
                                    if SFevent == "-Save_Folder-":
                                        
                                        # Get Selected Folder Path
                                        Folder_Path = SFvalues["-Selected_Folder_Path-"]

                                        # Origin Folder With Which The Mirror Standard Was Generated
                                        Current_Source_Folder = os.path.relpath(bc_values["Selected_Folder_Path"])

                                        # Relative Path Of Selected Folder 
                                        Relative_Path = os.path.relpath(Folder_Path, start = os.curdir)
                                        Relative_Path = Relative_Path.replace("\\","/")
                                        Current_Source_Folder = Current_Source_Folder.replace("\\","/")
                                        
                                        # Parent Path Of Selected Folder
                                        Parent_Path = os.path.dirname(Current_Source_Folder)

                                        # Auto-Generated Paths
                                        Results_Path = f"{Parent_Path}/Results"
                                        Thumbnails_Path = f"{Parent_Path}/Thumbnails"
                                        
                                        # Make Results and Thumbnail Folders
                                        os.makedirs(Results_Path, exist_ok=True)
                                        os.makedirs(Thumbnails_Path, exist_ok=True)

                                        # Update Other Setting Parameters
                                        c.execute(f"""UPDATE othsetctrl
                                                    SET NMS_Master_Pattern_Folder_Path = "{Relative_Path}", NMS_Master_Thumbnails_Folder_Path = "{Thumbnails_Path}", 
                                                    Result_Destination = "{Results_Path}", Origin_Pattern_Folder = "{Current_Source_Folder}"
                                                    WHERE rowid = 1""")

                                        # Commit Update Tranx
                                        conn.commit()

                                        # Refresh Data
                                        othset_data = database("othsetctrl")
                                        

                                        #########################
                                        # Generating Thumbnails #
                                        #########################

                                        New_NMS_Images = os.listdir(Relative_Path)
                                        BAR_MAX = len(New_NMS_Images)
                                        Thumb_close = False

                                        # layout the Window
                                        layout = [[sg.Text('Generating Thumbnail Files, \nCanceling May Lead To Loss Of Data')],
                                                [sg.ProgressBar(BAR_MAX, orientation='h', size=(35,10), key='-PROG-')]]

                                        # create the Window
                                        pmwindow = sg.Window('Progress Meter', layout, keep_on_top=True, finalize=True)

                                        # Create Properly Named Images
                                        for i,img in enumerate(tqdm(New_NMS_Images, desc = "Creating Thumbnail Files")):
                                            
                                            pmevent, pvalues = pmwindow.read(timeout=10)

                                            # Check For Window Close
                                            if pmevent == sg.WIN_CLOSED:
                                                Thumb_close = True
                                                break
                                            else:
                                                Thumb_closed = False

                                            Current_img = cv2.imread(f"{othset_data[6]}/{img}")
                                            resized_img = cv2.resize(Current_img, (Thumbnail_Width, Thumbnail_Height), interpolation=cv2.INTER_AREA)
                                            cv2.imwrite(f"{Thumbnails_Path}/{img}",resized_img)

                                            # Update Progress Bar
                                            pmwindow['-PROG-'].update(i+1)
                                        
                                        # done with loop... need to destroy the window as it's still open
                                        pmwindow.close()

                                        logger.debug("Update Concluded")

                                        #######################
                                        # Cleaning Thumbnails #
                                        #######################

                                        logger.debug("Checking For Unused Thumbnails")

                                        # Identifying Deleted Files
                                        Del_Files = [x for x in os.listdir(Thumbnails_Path) if x not in os.listdir(Relative_Path)]

                                        # Removing Thumbnails Of Deleted Stamdard Images
                                        if Del_Files != []:
                                            logger.debug("Clearing Unused Thumbnails")

                                            # layout the Window
                                            layout = [[sg.Text('Clearing Thumbnail Files, \nDo not cancel')],
                                                    [sg.ProgressBar(BAR_MAX, orientation='h', size=(35,10), key='-PROG-')]]

                                            # create the Window
                                            pmwindow = sg.Window('Progress Meter', layout, keep_on_top=True, finalize=True)

                                            for i,img in enumerate(tqdm(Del_Files, desc = "Removing Unused Thumbnails")):
                                                pmevent, pvalues = pmwindow.read(timeout=10)

                                                # Remove Unwanted Files
                                                os.remove(f"{Thumbnails_Path}/{img}")

                                                # Check For Window Close
                                                if pmevent == sg.WIN_CLOSED:
                                                    break

                                                # Update Progress Bar
                                                pmwindow['-PROG-'].update(i+1)
                                        
                                            # done with loop... need to destroy the window as it's still open
                                            pmwindow.close()
                                            
                                            logger.debug("Thumbails Cleared")

                                        # Activate Changes Notification
                                        sg.popup_auto_close("NOTIFICATION", "Changes Have Been Save", auto_close=True, auto_close_duration=int(3), keep_on_top=True)
                                    
                                # done with loop... need to destroy the window as it's still open
                                SFwindow.close()
                        
                        # Display Blank Screen When Not Capturing Images
                        if (Batch_Collect == False):
                            
                            # Show Blank Cropped Image Section
                            Blank_Stream = np.ones([bc_Height, bc_Width]) * 255
                            Blank_Stream_bytes = cv2.imencode('.png', Blank_Stream)[1].tobytes()
                            BATCH_CAPTURE_WIN['-BC_Image_Capture-'].update(data=Blank_Stream_bytes)

                        # Closing Analysis Window
                        if (bc_event == sg.WIN_CLOSED) or (bc_event == "CLOSE"):
                            logger.debug("Closing Batch Capture Window")

                            # Closing Camera Setting Window
                            Batch_Stream = False
                            BC_cap.release()
                            Batch_Active = False
                            BATCH_CAPTURE_WIN.close()
                            try:
                                bcp_view = False
                                BCP_WIN.close()
                            except:
                                pass
                            All_Threads.clear()

                            # Displaying Home Window
                            HOME_WIN.UnHide()
                            break

                else:
                    sg.Popup("Please Select An Available Camera", keep_on_top=True)

            # Camera Control Window
            if (home_event == "Set Up Camera"):

                # Hide Home Window
                HOME_WIN.Hide()

                # NMS Camera Window
                CC_VIEW_WIN, cc_view_Width, cc_view_Height = Camera_Control_View()
                logger.debug("Opening New Camera Control Window")

                # Camera Capture Variables
                Camera_Ctrl = True
                cap_on = False
                Track_Selector = ""

                while Camera_Ctrl:
                    cc_view_event, cc_view_values = CC_VIEW_WIN.read(timeout=5)

                    if Track_Selector != cc_view_values:
                        Track_Selector = copy.deepcopy(cc_view_values)
                        Camera_Start = True

                    if (Camera_Start == True) and (cc_view_values != None):
                        
                        # Identifying Camera Index
                        if cc_view_values[0] == True:
                            Selected_Camera = 0
                        
                        elif cc_view_values[1] == True:
                            Selected_Camera = 1
                        
                        elif cc_view_values[2] == True:
                            Selected_Camera = 2

                        if Cam_Test(Camera_Index = Selected_Camera) != True:

                            # Show Blank Cropped Image Section
                            Blank_Stream = np.ones([cc_view_Height, cc_view_Width]) * 255
                            Blank_Stream_bytes = cv2.imencode('.png', Blank_Stream)[1].tobytes()
                            CC_VIEW_WIN['Camera_Control_Display'].update(data=Blank_Stream_bytes)
                            Camera_Start = True
                            cap_on = False
                            
                            try:
                                CC_cap.release()
                            except:
                                pass
                        else:
                            # Start Camera
                            CC_cap = cv2.VideoCapture(Selected_Camera, cv2.CAP_DSHOW)

                            # Camera Focus Control
                            CC_cap.set(cv2.CAP_PROP_FOCUS, Current_Focus_Val)

                            # Camera Capture Set To Active
                            cap_on = True

                    # Check For Change In Camera Focus
                    if (cc_view_event != sg.WIN_CLOSED) and (rcv_data[3] != cc_view_values["-Focus Control-"]):
                        
                        # Round Focus To Nearest Value of 5
                        Value = round(cc_view_values["-Focus Control-"]/5)
                        Current_Focus_Val = Value*5

                        # Camera Focus Control
                        try: 
                            # Disable Camera Display
                            cap_on = False

                            # Release Camera
                            CC_cap.release()
                            
                            # Update Data From Database
                            rcv_data = list(rcv_data)
                            rcv_data[3] = cc_view_values["-Focus Control-"]
                            rcv_data = tuple(rcv_data) 

                            # Start Camera
                            CC_cap = cv2.VideoCapture(Selected_Camera, cv2.CAP_DSHOW)

                            # Camera Focus Control
                            CC_cap.set(cv2.CAP_PROP_FOCUS, Current_Focus_Val)

                            # Enable Camera Display
                            cap_on = True

                        except Exception as e:
                            logger.exception(str(e))
                    

                    # Display Video
                    if cap_on == True:
                        # Display Camera Video
                        ret, frame = CC_cap.read()
                        resize_cap = cv2.resize(frame, (cc_view_Width, cc_view_Height), interpolation=cv2.INTER_AREA)
                        cam_capbytes = cv2.imencode('.png',resize_cap)[1].tobytes()
                        CC_VIEW_WIN['Camera_Control_Display'].update(data=cam_capbytes)
                        Camera_Start = False


                    # Save Camera Control Setting
                    if (cc_view_event == "SAVE") and (Camera_Ctrl == True):

                        # Update Camera Control Parameters
                        c.execute(f"""UPDATE camctrl
                                    SET Camera_1 = {cc_view_values[0]}, Camera_2 = {cc_view_values[1]}, Camera_3 = {cc_view_values[2]}, Focus_Val = {Current_Focus_Val}
                                    WHERE rowid = 1""")

                        # Commit Update Tranx
                        conn.commit()

                    # Closing Camera Control Window
                    if (cc_view_event == sg.WIN_CLOSED) or (cc_view_event == "CLOSE"):
                        logger.debug("Closing Camera Control Window")
                        
                        # Closing Camera Use
                        try:
                            CC_cap.release()
                        except:
                            pass

                        # Closing Camera Setting Window
                        Camera_Ctrl = False
                        CC_VIEW_WIN.close()

                        # Displaying Home Window
                        HOME_WIN.UnHide()
                        break

            # Other Settings
            if (home_event == "Other Settings"):
                
                # Hiding Home Window
                HOME_WIN.Hide()

                # NMS Camera Window
                OS_VIEW_WIN, OS_Width, OS_Height = Other_Setting_View()
                logger.debug("Showing Pattern Folder")

                # Other Setting Display Variables
                os_view = True

                while os_view:
                    os_view_win_event, os_view_win_values = OS_VIEW_WIN.read()

                    # Save Other Settings
                    if (os_view_win_event == "SAVE"):
                        
                        # Integer Equivalent of Bbox_Line_Width Selection
                        Index_Value = (Bbox_Width_List.index(os_view_win_values["-Set_Bbox_Width-"]) + 1)

                        # Integer Equivalent of Bbox Dimensions
                        Thumbnail_Dimension_Dict = {
                            "50 by 50 Pixels":50, 
                            "100 by 100 Pixels":100, 
                            "150 by 150 Pixels":150
                            }

                        Thumbnail_Value = Thumbnail_Dimension_Dict[os_view_win_values["-Set_Thumbnail_Dimension-"]]

                        # Auto-Generate Thumbnails and Results Default Destination
                        Selected_Default_Pattern_Folder_Path = os_view_win_values["-Set_Master_Folder-"]
                        
                        # Relative Path Of Selected Folder 
                        Relative_Path = os.path.relpath(Selected_Default_Pattern_Folder_Path, start = os.curdir)
                        Relative_Path = Relative_Path.replace("\\","/")
                        
                        # Parent Path Of Selected Folder
                        Parent_Path = os.path.dirname(Relative_Path)

                        # Auto-Generated Paths
                        Results_Path = f"{Parent_Path}/Results"
                        Thumbnails_Path = f"{Parent_Path}/Thumbnails"

                        # Update Other Setting Parameters
                        c.execute(f"""UPDATE othsetctrl
                                    SET Timer = "{os_view_win_values["-Time_Delay-"]}", Log_Level = "{os_view_win_values["-Set_Log_Level-"]}", 
                                    Bbox_Line_Width = {Index_Value}, Bbox_Line_Colour = "{os_view_win_values["-Set_Bbox_Color-"]}", Thumbnails_Width = {Thumbnail_Value},
                                    Thumbnails_Height = {Thumbnail_Value}, NMS_Master_Pattern_Folder_Path = "{Relative_Path}",
                                    NMS_Master_Thumbnails_Folder_Path = "{Thumbnails_Path}", Result_Destination = "{Results_Path}"
                                    WHERE rowid = 1""")

                        # Commit Update Tranx
                        conn.commit()

                        # Refresh Other Settings Data
                        othset_data = database["othsetctrl"]

                        # Activate Changes Notification
                        sg.Popup("NOTIFICATION", "Restart App To Activate Changes", keep_on_top=True)



                    # Closing OS Window
                    if (os_view_win_event == sg.WIN_CLOSED) or (os_view_win_event == "CLOSE"):
                        logger.debug("Closing Other Setting Window")

                        # Closing Camera Setting Window
                        os_view = False
                        OS_VIEW_WIN.close()

                        # Displaying Home Window
                        HOME_WIN.UnHide()
                        break
            """
            Currently working on multi-bbox display and capture
            """
            # Start Operation
            if (home_event == "START"):

                # File Save Variables
                required_data = database("othsetctrl")
                Origin_Path = required_data[9]
                Parent_Folder = required_data[8]
                Storage_Path = Folder_Create(Parent_Folder)
                Returned_Values = list()
                Sample_Count = 0

                # Creating Collection Folder
                if home_values["Sample_ID"] == "":
                    Returned_Values = Create_Collection(Storage_Path)


                else:
                    Custom_Folder_Path = f"{Storage_Path}/{home_values['Sample_ID']}"
                    Returned_Values.append(home_values["Sample_ID"])
                    Returned_Values.append(Storage_Path)
                    try:
                        os.makedirs(Custom_Folder_Path)
                        sg.Popup(f"Using Collection Name {home_values['Sample_ID']} at Location {Custom_Folder_Path}", keep_on_top=True, background_color="green")
                        Activate = True
                    
                    except FileExistsError:
                        sg.Popup("NOTIFICATION",f"Using Previously Created Folder",keep_on_top=True, background_color="brown")
                        Activate = True
                    
                    except Exception as e:
                        logger.exception(str(e))
                        sg.Popup("NOTIFICATION",f"Unable To Create Collection Folder, {str(e)}",keep_on_top=True, background_color="red")
                        Activate = False


                # Clear Tracking Thread
                All_Threads.clear()

                # Hiding Home Window
                HOME_WIN.Hide()

                #######################
                ## MAIN APP SECTION
                #######################

                # Starting Operation Variables
                Auto_Start = True
                Manual_Start = False
                Thread_Control = True
                Single_Run = False

                # Main App Section Window
                MAIN_APP_WIN, MAS_Width, MAS_Height = Main_App_Section()
                logger.debug("Starting Main App")

                # Start Camera
                MAS_cap = cv2.VideoCapture(Selected_Camera, cv2.CAP_DSHOW)

                # Camera Focus Control
                MAS_cap.set(cv2.CAP_PROP_FOCUS, Current_Focus_Val)
                Camera_State = "On"

                # Database Connection
                MAS_Data = database("nmsctrl")
                Mode = MAS_Data[12]

                # SSIM Collector
                SSIM_List = list()
                SSIM_DATA_POINTS = list()
                Average_SSIM = 0

                # Create Storage Folder
                Destination_Folder = f"{Returned_Values[1]}/{Returned_Values[0]}/run_{len(os.listdir(f'{Returned_Values[1]}/{Returned_Values[0]}')) + 1}"
                os.makedirs(Destination_Folder)

                ######################
                ## PATTERN WINDOW
                ######################

                # Pattern Origin Folder
                MAS_Source_Folder = f"{required_data[9]}"

                # Select Thumbnail File To be highlighted
                Thumbnail_Files = os.listdir(NMS_Master_Thumbnails_Folder)
                Thumbnail_Files.sort(key=natural_keys)

                # Refresh Default Display Pattern
                Default_Pattern = f"{MAS_Source_Folder}/{Thumbnail_Files[0]}"

                # Activate Pattern View Window
                PATTERN_VIEW_WIN, PV_Width, PV_Height = Batch_Capture_Pattern(Default_Pattern = Default_Pattern)
                print(f"Currently Displaying {Default_Pattern}")
                pattern_view = True

                while Activate:
                    # Read Main App Event
                    mas_event,mas_values = MAIN_APP_WIN.read(timeout=5)

                    # Auto Start Main App Running
                    if Camera_State == "On" and Auto_Start == True:
                        # Display Camera Video
                        ret, frame = MAS_cap.read()
                        resize_cap = cv2.resize(frame, (MAS_Width, MAS_Height), interpolation=cv2.INTER_AREA)
                        cam_capbytes = cv2.imencode('.png',resize_cap)[1].tobytes()
                        MAIN_APP_WIN['-MAS_Camera_Display-'].update(data=cam_capbytes)

                    # Activate Single Run Mode
                    if mas_event == "-MAS_SingleRun_Button-":
                        All_Threads.clear()
                        Exit_Thread.clear()
                        Auto_Start = True
                        Single_Run = True
                        sg.popup("NOTIFICATION", "Single Run Mode Is Now Active.", keep_on_top=True)

                    # ReActivate Full Auto Mode
                    if mas_event == "-MAS_Start_Button-":
                        All_Threads.clear()
                        Exit_Thread.clear()
                        Auto_Start = True
                        Single_Run = False
                        sg.popup("NOTIFICATION", "Running Auto Mode", keep_on_top=True)

                    # Activate Manual Mode
                    if mas_event == "-MAS_Manual_Button-":
                        Exit_Thread.clear()

                        # Set Manual Control Parameters
                        Auto_Start = False
                        Manual_Start = True

                        # Clean Thread Control
                        All_Threads.clear()

                        # Create Countdown Threads
                        if len(All_Threads) == 0:    
                            All_Threads.append(threading.Thread(target=countdown, args=(MAIN_APP_WIN, Count_Down_Timer, Manual_Start, Auto_Start), daemon=True).start())
                                
                    # Stop Operation
                    if mas_event == "-MAS_Stop_Button-":
                        Auto_Start = False
                        Manual_Start = False
                        Exit_Thread.set()
                        All_Threads.clear()

                    if (Auto_Start == True) and (Thread_Control == True):
                        # Stop Manual Control
                        Manual_Start = False

                        # Create Countdown Threads
                        if len(All_Threads) == 0:    
                            All_Threads.append(threading.Thread(target=countdown, args=(MAIN_APP_WIN, Count_Down_Timer,Manual_Start, Auto_Start), daemon=True).start())
                                
                    # Updating Count Down On Display
                    if mas_event == "-THREAD_TIMER-":
                        MAIN_APP_WIN["-MAS_Timer_Time-"].update(mas_values["-THREAD_TIMER-"])

                    # Activate SSIM Analysis
                    if (mas_event == "-SSIM_ACTIVATE-"):
                        
                        # Update Pattern Count Widget
                        Number_of_Patterns = Number_of_Patterns - 1
                        MAIN_APP_WIN["-MAS_Pattern_Count-"].update(Number_of_Patterns)
                        
                        # Update Sample Count Widget
                        Sample_Count += 1

                        # Clear Tracking Thread
                        All_Threads.clear()

                        # Check To Verify Pattern Window
                        if pattern_view != False:
                        
                            # Image Capture
                            Camera_State = "Picture Mode"

                            # Synched Bbox Parameters
                            Xmin = int(MAS_Data[2])
                            Ymin = int(MAS_Data[4])
                            Xmax = int(MAS_Data[3])
                            Ymax = int(MAS_Data[5])

                            # Bbox Parameters
                            Start_point = (Xmin,Ymin)
                            End_point = (Xmax,Ymax)
                            color = Bbox_Line_Color
                            line_width = Bbox_Line_Width

                            # Apply Bbox Image To Section
                            MAS2_cap = cv2.VideoCapture(Selected_Camera, cv2.CAP_DSHOW)
                            ret, sec_frame = MAS2_cap.read()
                            MAS2_cap.release()
                            print("Taking Picture Of Pattern Displayed")

                            # Copy Frame
                            copy_frame = copy.deepcopy(sec_frame)
                            
                            # Update Display Window
                            MAS_Image = cv2.rectangle(copy_frame, Start_point, End_point, color, line_width)
                            Resized_MAS_Image = cv2.resize(MAS_Image, (MAS_Width, MAS_Height), interpolation=cv2.INTER_AREA)
                            Resized_MAS_Image_imgbytes = cv2.imencode('.png', Resized_MAS_Image)[1].tobytes()
                            MAIN_APP_WIN['-MAS_Camera_Display-'].update(data=Resized_MAS_Image_imgbytes)

                            # Get File
                            Thumbnail_File = Thumbnail_Files[Sample_Count-1]

                            # Origin_Folder
                            MAS_Origin_Folder = required_data[9]
                            
                            # Folder Paths
                            print("Updating Images")
                            try:
                                Origin_File_Path = f"{MAS_Origin_Folder}/{Thumbnail_Files[Sample_Count]}"
                            except IndexError:
                                Origin_File_Path = f"{MAS_Origin_Folder}/{Thumbnail_Files[0]}"
                            Pattern_File_Path = f"{NMS_Master_Pattern_Folder}/{Thumbnail_File}"
                            Thumbnail_File_Path= f"{NMS_Master_Thumbnails_Folder}/{Thumbnail_File}"

                            try:
                                Returned_List = Thumbnails_Refresh(PATTERN_VIEW_WIN, PV_Width, PV_Height, None, Pattern_File_Path, Thumbnail_File_Path, Origin_File_Path=Origin_File_Path, Refresh=False, Bbox = "Active", Image_List = Thumbnail_Files)

                                # Get Cropped Pattern Section
                                Cropped_Pattern = Returned_List[1]

                                # Get Cropped Image Section
                                MAS_Cropped_Section = sec_frame[Ymin:Ymax, Xmin:Xmax]
                                
                                # Carry Out SSIM TEST
                                (Result, diff) = compare_ssim(MAS_Cropped_Section, Cropped_Pattern, full=True, multichannel=True)
                                logger.debug("SSIM Computed")
                                logger.debug(f"Test Result is {Result}")
                                SSIM_List.append(Result)

                                # Get Pattern_Id
                                Id_Split = Thumbnail_File.split("_")
                                Id = Id_Split[0]
                                
                                # Save Cropped Image
                                cv2.imwrite(f"{Destination_Folder}/{Id}_Image.png", MAS_Cropped_Section)

                                # Save Cropped Pattern
                                cv2.imwrite(f"{Destination_Folder}/{Id}_Pattern.png", Cropped_Pattern)

                                # Save Full Scale Image
                                cv2.imwrite(f"{Destination_Folder}/{Id}_FullScale_Image.png", MAS_Image)

                                # Save Full Scale Pattern
                                cv2.imwrite(f"{Destination_Folder}/{Id}_FullScale_Pattern.png", Returned_List[0])

                                # Collection SSIM
                                Total = 0
                                SSIM_List_Length = len(SSIM_List)

                                for SSIM in SSIM_List:
                                    Total = Total + SSIM

                                Average_SSIM = Total/SSIM_List_Length

                                # Display Current SSIM result
                                MAIN_APP_WIN["-MAS_Single_SSIM_Result-"].Update(round(Result,6))
                                MAIN_APP_WIN["-MAS_Overall_SSIM_Result-"].Update(round(Average_SSIM,6))

                                # Create Annotation Files
                                Annotation_Folder_Path = f"{Destination_Folder}/ANNOTATION"
                                os.makedirs(Annotation_Folder_Path, exist_ok=True)

                                # Write To Annotation
                                if os.path.exists(f'{Annotation_Folder_Path}/Annotation.csv'):
                                    with open(f'{Annotation_Folder_Path}/Annotation.csv', 'a', newline='') as file:
                                        writer = csv.writer(file)
                                        writer.writerow([Id, f"{Id}_Image.png", f"{Id}_Pattern.png", Result, Average_SSIM])
                                else:
                                    with open(f'{Annotation_Folder_Path}/Annotation.csv', 'w+', newline='') as file:
                                        writer = csv.writer(file)
                                        writer.writerow(["SN", "Image_Name", "Pattern_Name", "SSIM_Value","Current Average Value"])
                                        writer.writerow([Id, f"{Id}_Image.png", f"{Id}_Pattern.png", Result, Average_SSIM])

                            except Exception as e:
                                sg.Popup(f"Unable To Focus Pattern {e}", keep_on_top=True)
                                logger.exception(f"Focus Pattern Window Error {str(e)}")

                        else:
                            sg.Popup("PATTERN WINDOW","Pattern Window Needs To Be Active, Please Close Window and Click START", keep_on_top=True)

                        # Reset Counters
                        if Sample_Count == Pattern_Count:

                            # Useful Variables
                            # print(f"Data Points For Run_{len(os.listdir(f'{Returned_Values[1]}/{Returned_Values[0]}'))}")
                            # print(SSIM_DATA_POINTS)
                            # print(f"Overall Average After {Sample_Count} Patterns is {Average_SSIM}")

                            # Reset Variables
                            Sample_Count = 0
                            Number_of_Patterns = copy.deepcopy(Pattern_Count)
                            Collection_Count += 1

                            # Update Counter Widgets 
                            MAIN_APP_WIN["-MAS_Pattern_Count-"].update(Number_of_Patterns)
                            MAIN_APP_WIN["-MAS_Collection_Count-"].Update(Collection_Count)

                            # Clear Collection_List
                            SSIM_List.clear()

                            # Stop App On Single Run
                            if (Single_Run == True):
                                
                                # Terminate Auto Run 
                                Auto_Start = False 
                                logger.debug("Terminated Auto Run")
                                sg.popup('NOTIFICATION', "Click 'SINGLE RUN' To Start New Count Down.", keep_on_top=True)
                            
                            else:    
                                # Create New Storage Folder
                                Destination_Folder = f"{Returned_Values[1]}/{Returned_Values[0]}/run_{len(os.listdir(f'{Returned_Values[1]}/{Returned_Values[0]}')) + 1}"
                                os.makedirs(Destination_Folder, exist_ok=True)


                    # Close MAS window
                    if (mas_event == sg.WIN_CLOSED) or (mas_event == "-MAS_Exit_Button-"):
                        logger.debug("Closing Main App Section")

                        # Closing Camera Setting Window
                        Thread_Control= False
                        All_Threads.clear()
                        Exit_Thread.clear()

                        try:
                            PATTERN_VIEW_WIN.close()
                            pattern_view = False
                            logger.debug("Closed Pattern Window Only")
                        except:
                            sg.Popup("Closed Window", "Pattern Window Has Already Been Closed", keep_on_top=True)

                        MAS_cap.release()
                        MAIN_APP_WIN.close()


                        # Displaying Home Window
                        HOME_WIN.UnHide()
                        break

                    #  Run Only If Pattern Window is Active 
                    if pattern_view == True:

                        # Read Pattern View Event
                        pv_event, pv_values = PATTERN_VIEW_WIN.read(timeout=10)

                        # Close Pattern View Window
                        if (pv_event == sg.WIN_CLOSED) or (pv_event == "CLOSE"):
                            PATTERN_VIEW_WIN.close()
                            pattern_view = False
                            logger.debug("Closed Pattern Window Only")

            # View Previous Analysis
            if (home_event == "-Previous_Analysis-"):

                # Get Current Results Folder
                othset_data = database("othsetctrl")
                Analysis_Results_Folder = f"{othset_data[8]}"

                # Hiding Home Window
                HOME_WIN.Hide()

                # Analysis Window Parameters
                Analysis_Window = True
                Selected_Date = ""
                Selected_Collection = ""

                # Analysis Window
                ANALYSIS_APP_WIN, ANALYSIS_Width, ANALYSIS_Height = Analysis_View()

                while Analysis_View:
                    analysis_event, analysis_value = ANALYSIS_APP_WIN.read()

                    # # Selecion Button For Date Buttons
                    # if (analysis_event != None) and (analysis_event.startswith("Date")):
                    #     get_date = analysis_event.split("_")
                    #     Dates = os.listdir(Analysis_Results_Folder)
                    #     for Date in Dates:
                    #         ANALYSIS_APP_WIN[f"Collection_{Date}"].update(visible = False)    
                    #     ANALYSIS_APP_WIN[f"Collection_{get_date[1]}"].update(visible = True)
                    #     Selected_Date = get_date[1]

                    # # Selection Button For Collection Folder
                    # if (analysis_event != None) and (analysis_event.startswith("Collection")):
                    #     get_collection = analysis_event.split("Collection_")
                    #     Selected_Collection = get_collection[1]
                    
                    # View Image Section
                    if (analysis_event != None) and (analysis_event.endswith(".png")):
                        
                        # Open Individual Cropped Image
                        if os.path.isfile(analysis_event):
                            
                            # Helps Activate The Image Display Section
                            Image_View = True
                            
                            # Open Image View Window
                            IMAGE_WIN, IMAGE_WIN_Width, IMAGE_WIN_Height = Image_View_Win(Image_Path = analysis_event)

                            while Image_View:
                                Image_Event, Image_Value = IMAGE_WIN.read()

                                if(Image_Event == sg.WIN_CLOSED):
                                    IMAGE_WIN.close()
                                    Image_View = False

                        else:
                            try:
                                Event_Split = analysis_event.split(",")

                                # Helps Activate The Image Display Section
                                Dual_Image_View = True
                                
                                # Open Image View Window
                                IMAGE_WIN, IMAGE_WIN_Width, IMAGE_WIN_Height = Image_View_Win(Image_Path = analysis_event, Dual=True, Img1 = Event_Split[0], Img2 = Event_Split[1])

                                while Dual_Image_View:
                                    Dual_Image_Event, Dual_Image_Value = IMAGE_WIN.read()

                                    if(Dual_Image_Event == sg.WIN_CLOSED):
                                        IMAGE_WIN.close()
                                        Dual_Image_View = False
                            
                            except Exception as e:
                                sg.popup(f"Unable To Display The Selected Image {e}", title = "Invalid File", keep_on_top=True)

                    # Closing Analysis Window
                    if (analysis_event == sg.WIN_CLOSED) or (analysis_event == "CLOSE"):
                        logger.debug("Closing Analysis Window")

                        # Closing Camera Setting Window
                        Analysis_Window = False
                        ANALYSIS_APP_WIN.close()

                        # Displaying Home Window
                        HOME_WIN.UnHide()
                        break

            # Closing Application
            if (home_event == sg.WIN_CLOSED) or (home_event == "CLOSE"):
                logger.debug("Closing Home Window")
                HOME_WIN.close()
                break

            # View All Origin Images
            if (home_event == "View Origin Images"):
                
                # Other Setting Database Connection
                othset_data = database("othsetctrl")

                # Refresh Info From DB
                Thumbnail_Files = os.listdir(NMS_Master_Thumbnails_Folder)
                Thumbnail_Files.sort(key=natural_keys)

                # NMS Master Folder
                VOI_Origin_Folder = f"{othset_data[9]}"
                Default_Pattern = f"{VOI_Origin_Folder}/{os.listdir(NMS_Master_Thumbnails_Folder)[0]}"

                # NMS Pattern Window
                try:
                    # Hiding Home Window
                    HOME_WIN.Hide()

                    VOI_WIN, voi_Width, voi_Height = NMS_Pattern_View(Default_Pattern=Default_Pattern)
                    logger.debug("Opening Pattern Origin View")

                    # Origin View Control
                    origin_view = True

                except:
                    sg.popup("No Image File In Origin Folder, Please Collect New Batch Data", title = "NOTOFICATION", keep_on_top=True)
                    
                    # Unhiding Home Window
                    HOME_WIN.UnHide()
                
                else:
                    # Operaton Loop
                    while origin_view:
                        voi_event, voi_values = VOI_WIN.read(timeout=10)

                        # Change Displayed Pattern
                        if (voi_event != sg.WIN_CLOSED) and (voi_event != "__TIMEOUT__"):
                            
                            # Folder Paths
                            Pattern_File_Path = f"{VOI_Origin_Folder}/{voi_event}"
                            Thumbnail_File_Path= f"{NMS_Master_Thumbnails_Folder}/{voi_event}"

                            # Display Pattern Image
                            try:
                                Thumbnails_Refresh(VOI_WIN, voi_Width, voi_Height, voi_event, Pattern_File_Path, Thumbnail_File_Path, Image_List = os.listdir(NMS_Master_Thumbnails_Folder))
                            
                            except Exception as e:
                                sg.Popup(f"File Does Not Exist {e}", keep_on_top=True)
                                logger.exception(str(e))

                        # Closing Pattern Window
                        if(voi_event == sg.WIN_CLOSED):
                            VOI_WIN.close()
                            origin_view = False
                            logger.debug("Closed Pattern Window Only")
                            
                            # Unhiding Home Window
                            HOME_WIN.UnHide()


    except Exception as e:
        logger.exception(str(e))
