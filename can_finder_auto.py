import serial
import time
import tkinter as tk
import threading
import queue
from datetime import datetime
import os
import sys
import struct


def getHx(data):
    return struct.unpack("B", data)[0]

def getDe(data):
    try:
        de = data.decode()
    except:
        de = None

    return de


def readData():
    global interrupt, messageList, processQ

    ser.read(ser.in_waiting)
    while getDe(ser.read(1)) != 'X' or getDe(ser.read(1)) != 'X':
        pass

    while not interrupt:
        try:
            string = ser.read(50)

            processQ.put(string)
        except:
            print("ERROR")

def processData():
    global interrupt, processQ, displayQ, requestData, logFile, doLog

    messages = {}
    messageBytes = None
    messagesString = ""

    id = 0
    dlc = 0
    data = ""
    currentProgress = 0

    errorText = ""

    while not interrupt:
        try:
            messageBytes = processQ.get()

            messagesString = ("".join([str(bt) + " " for bt in messageBytes])).strip().split('88 88')

            while '' in messagesString:
                messagesString.remove('')

            for msg in messagesString:
                try:
                    msgBytes = msg.strip().split(' ')
                    if currentProgress == 0 and msgBytes[0] == '88':
                        del(msgBytes[0])
                    i = 0
                    while i < len(msgBytes):
                        if currentProgress % 2 == 1:
                            if msgBytes[i] != str(currentProgress):
                                errorText = "Missing gap marker (0)"
                                raise
                        elif currentProgress == 0:
                            id = int(msgBytes[i]) << 8
                            if id > 2047:               # max 11 bit
                                errorText = "ID > 2047"
                                raise
                        elif currentProgress == 2:
                            id += int(msgBytes[i])
                        elif currentProgress == 4:
                            dlc = int(msgBytes[i])
                            if dlc > 8:                 # dlc max 8
                                errorText = "DLC > 8"
                                raise
                        elif currentProgress >= 6:
                            data += f"{int(msgBytes[i]):x} "

                        currentProgress += 1

                        i += 1

                        if currentProgress >= 6 + dlc * 2:
                            if currentProgress == 6 + dlc * 2 and len(msgBytes) <= i + 1:

                                messages[f"{id:x}"] = f"{dlc:x} {data}"
                                if doLog:
                                    logFile.write(f"{datetime.now().time()}>{id:x} {dlc:x} {data}\n")
                                currentProgress = 0
                                data = ""
                                i += 1                  # stop iteration when last byte is 88 ('X')
                            else:
                                errorText = "Too few / too many bytes for 1 frame"
                                raise
                except:
                    print(f"VALUE ERROR ({errorText}):")
                    # print(f"\tFRAME: {msgBytes}")
                    # print(f"\tID: {id} DLC: {dlc} DATA: {data}")
                    # print(f"\tIDX: {i} PRG: {currentProgress}")
                    currentProgress = 0
                    data = ""
        except Exception as e:
            print(f"ERROR - {e}")

        if requestData:
            requestData = False
            messages = dict(sorted(messages.items(), key=lambda x: int(x[0], 16)))
            displayQ.put(messages.copy())

def displayData():
    global interrupt, requestData, displayQ, logFile

    oldMessage = {}

    while not interrupt:
        requestData = True
        message = displayQ.get()

        scrollPos = LBMessages.yview()[0]
        i = 0
        messagesText = ""
        for key in message:
            try:
                dlc, data = message[key].split(' ', 1)
                if key in oldMessage:
                    _, oldData = oldMessage[key].split(' ', 1)

                    if oldData != data:
                        messagesText += "{}\t{}   {}\n\n".format(key, dlc, data)
            except:
                print(f"ERROR while displaying data: {key} - {message[key]}")
            i += 1

        oldMessage = message

        LBMessages.delete(1.0,"end")
        LBMessages.insert(1.0, messagesText)

        LBMessages.yview_moveto(scrollPos)

        time.sleep(0.1)

def logging():
    global btnLog, doLog, logFile

    if not doLog:
        if not os.path.exists("logs/"):
            os.mkdir("logs")
        logFile = open("logs/log_{}.txt".format(datetime.now().strftime("%m%d_%H%M%S")), "w")
        doLog = True
        btnLog.config(bg='red', text="STOP LOG")
    else:
        doLog = False
        btnLog.config(bg='lime', text="START LOG")
        logFile.close()

############################################################################### START ###############################################################################

print("\n")             # make space on the terminal

interrupt = False
requestData = False
doLog = False
displayQ = queue.Queue()
processQ = queue.Queue()

logFile = None
messageList = []

root = tk.Tk()
root.geometry("600x600")

LBMessages = tk.Text(root, width=80, font=("Courier", 16))
scrollbar = tk.Scrollbar(root, orient="vertical", command=LBMessages.yview)
btnLog = tk.Button(root, text="START LOG", command = logging, width=80, height=1, bg='lime', font=("Courier", 16))

btnLog.pack(pady=3)
scrollbar.pack(side="right", fill="y")
LBMessages.pack(side="left",fill="y")

ser = serial.Serial('COM13', 500000, timeout=1)
time.sleep(2)

readThread = threading.Thread(target=readData)
processThread = threading.Thread(target=processData)
displayThread = threading.Thread(target=displayData)

processThread.daemon = True
displayThread.daemon = True

readThread.start()
processThread.start()
displayThread.start()

root.mainloop()

interrupt = True
time.sleep(1)

ser.close()
