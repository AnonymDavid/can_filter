import serial
import time
import tkinter as tk
import threading
import queue
import struct

### GET VALUE FROM BYTE ###
def getHx(data):
    return struct.unpack("B", data)[0]

### GET ASCII FROM BYTE ###
def getDe(data):
    try:
        de = data.decode()
    except:
        de = None
    
    return de

### DATA READING THREAD ###
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

### PROCESS THREAD ###
def processData():
    global interrupt, processQ, displayQ, requestData, doSnapshot
    
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
                                currentProgress = 0
                                data = ""
                                i += 1                  # stop iteration when last byte is 88 ('X')
                            else:
                                errorText = "Too few / too many bytes for 1 frame"
                                raise
                except:
                    print(f"VALUE ERROR ({errorText})")
                    # print(f"\tFRAME: {msgBytes}")
                    # print(f"\tID: {id} DLC: {dlc} DATA: {data}")
                    # print(f"\tIDX: {i} PRG: {currentProgress}")
                    currentProgress = 0
                    data = ""
        except Exception as e:
            print(f"ERROR - {e}")
        
        if requestData:
            requestData = False
            
            displayQ.put(messages.copy())

### DISPLAY THREAD ###
def displayData():
    global interrupt, requestData, displayQ, LBMessages, doSnapshot, changeType, idFilters, checkboxValues, chkBoxes, rbFilters, filterType

    snapshot = {}
    checkedFilterCount = 0
    requiredPassedBytes = 0

    while not interrupt:
        requestData = True
        message = displayQ.get()
        
        ##################### SNAPSHOT #####################
        if len(message) == 1 and message[0] == "reset":
            for rb in rbFilters:
                rb['state'] = 'normal'

            for box in chkBoxes:
                box['state'] = 'normal'
            
            for boxValue in checkboxValues:
                boxValue.set(1)
            
            idFilters = []

            snapshot = {}

            changeType = 'x'

            continue
        
        if len(snapshot) == 0:          # no snapshot yet
            idFilters = list(message.keys())
        if doSnapshot:
            doSnapshot = False

            if len(snapshot) > 0:
                if filterType.get() == '2':
                    newFilters = []
                    for key in idFilters:
                        newData = [int(bt, 16) for bt in message[key].split(' ')[:-1]]
                        oldData = [int(bt, 16) for bt in snapshot[key].split(' ')[:-1]]

                        i = 1
                        newSum = 0
                        oldSum = 0
                        while i <= newData[0]:
                            if checkboxValues[i - 1].get() == 1:
                                newSum += newData[i]
                                oldSum += oldData[i]
                            i += 1

                        if (
                            (changeType == 'm' and newSum > oldSum) or 
                            (changeType == 'l' and newSum < oldSum) or 
                            (changeType == 'u' and newSum == oldSum)
                            ):
                            newFilters.append(key)
                    idFilters = newFilters
                else:
                    newFilters = []
                    for key in idFilters:
                        newData = [int(bt, 16) for bt in message[key].split(' ')[:-1]]
                        oldData = [int(bt, 16) for bt in snapshot[key].split(' ')[:-1]]

                        passedBytes = 0
                        i = 1
                        while i <= newData[0] and passedBytes < requiredPassedBytes:
                            if checkboxValues[i - 1].get() == 1:
                                if (
                                    (changeType == 'm' and newData[i] > oldData[i]) or 
                                    (changeType == 'l' and newData[i] < oldData[i]) or 
                                    (changeType == 'u' and newData[i] == oldData[i])
                                ):
                                    passedBytes += 1
                            i += 1

                        if passedBytes >= requiredPassedBytes:        
                            newFilters.append(key)
                    idFilters = newFilters
            else:
                checkedFilterCount = sum([x.get() for x in checkboxValues])
                requiredPassedBytes = (1 if filterType.get() == '0' else checkedFilterCount)
            snapshot = message
        
        ####################################################

        scrollPos = LBMessages.yview()[0]
        i = 0
        messagesText = f"FRAME COUNT: {len(idFilters)}\n\nID     DLC       DATA\n"
        for key in idFilters:
            try:
                dlc, data = message[key].split(' ', 1)
                messagesText += "{}\t{}  {}\n".format(key, dlc, data)
            except:
                print(f"ERROR while displaying data: {key} - {message[key]}")
            i += 1

        LBMessages.delete(1.0,"end")
        LBMessages.insert(1.0, messagesText)

        LBMessages.yview_moveto(scrollPos)
        
        time.sleep(0.1)

### SNAPSHOT BUTTON CLICK EVENT ###
def snapshot_event():
    global btnSnapshot, doSnapshot, btnMore, btnUnchanged, btnLess, btnClearFilters, chkBoxes, rbFilters

    btnSnapshot['state'] = 'disabled'
    btnSnapshot['bg'] = 'gray'

    btnMore['state'] = 'normal'
    btnMore['bg'] = 'lime'
    
    btnUnchanged['state'] = 'normal'
    btnUnchanged['bg'] = '#CCCCCC'
    
    btnLess['state'] = 'normal'
    btnLess['bg'] = 'red'
    
    btnClearFilters['state'] = 'normal'
    btnClearFilters['bg'] = 'cyan'

    for rb in rbFilters:
        rb['state'] = 'disabled'
    
    for box in chkBoxes:
        box['state'] = 'disabled'
    
    doSnapshot = True

### CLEAR BUTTON CLICK EVENT ###
def clearFilters_event():
    global btnSnapshot, btnMore, btnUnchanged, btnLess, btnClearFilters, chkBoxes, displayQ

    btnSnapshot['state'] = 'normal'
    btnSnapshot['bg'] = 'magenta'

    btnMore['state'] = 'disabled'
    btnMore['bg'] = 'gray'
    
    btnUnchanged['state'] = 'disabled'
    btnUnchanged['bg'] = 'gray'
    
    btnLess['state'] = 'disabled'
    btnLess['bg'] = 'gray'
    
    btnClearFilters['state'] = 'disabled'
    btnClearFilters['bg'] = 'gray'

    displayQ.put(["reset"])


### LESS BUTTON CLICK EVENT ###
def less_event():
    global changeType, doSnapshot

    changeType = 'l'

    doSnapshot = True

### MORE BUTTON CLICK EVENT ###
def more_event():
    global changeType, doSnapshot

    changeType = 'm'

    doSnapshot = True

### UNCHANGED BUTTON CLICK EVENT ###
def unchanged_event():
    global changeType, doSnapshot

    changeType = 'u'

    doSnapshot = True


############################## START ##############################

print("\n")             # make space on the terminal

### VARIABLES ###
interrupt = False
requestData = False
doSnapshot = False

displayQ = queue.Queue()
processQ = queue.Queue()

changeType = 'x'

idFilters = []
messageList = []

root = tk.Tk()
root.geometry("600x700")

filterTypes ={
    "Individual": "0",
    "Strict": "1",
    "Sum": "2"
}

filterType = tk.StringVar(root, "0")
checkboxValues = [tk.IntVar(value=1) for i in range(8)]

LBMessages = tk.Text(root, width=35, font=("Courier", 15))
scrollbar = tk.Scrollbar(root, orient="vertical", command=LBMessages.yview)

### BUTTONS ###
btnSnapshot = tk.Button(root, text="Snapshot", command = snapshot_event, width=12, height=2, bg='magenta', font=("Arial", 12, "bold"))
btnMore = tk.Button(root, text="^", command = more_event, width=10, height=2, bg='gray', font=("Arial", 10, "bold"), state='disabled')
btnUnchanged = tk.Button(root, text="-", command = unchanged_event, width=10, height=2, bg='gray', font=("Arial", 10, "bold"), state='disabled')
btnLess = tk.Button(root, text="v", command = less_event, width=10, height=2, bg='gray', font=("Arial", 10, "bold"), state='disabled')
btnClearFilters = tk.Button(root, text="Clear all filters", command = clearFilters_event, width=12, height=2, bg='gray', font=("Arial", 12, "bold"), state='disabled')

### FILTERS ###
rbFilters = [tk.Radiobutton(root, text = text, variable = filterType, value = value, indicator = 0, background = "light blue") for (text, value) in filterTypes.items()]

chkBoxes = [
    tk.Checkbutton(root, text='D1', variable=checkboxValues[0], onvalue=1, offvalue=0),
    tk.Checkbutton(root, text='D2', variable=checkboxValues[1], onvalue=1, offvalue=0),
    tk.Checkbutton(root, text='D3', variable=checkboxValues[2], onvalue=1, offvalue=0),
    tk.Checkbutton(root, text='D4', variable=checkboxValues[3], onvalue=1, offvalue=0),
    tk.Checkbutton(root, text='D5', variable=checkboxValues[4], onvalue=1, offvalue=0),
    tk.Checkbutton(root, text='D6', variable=checkboxValues[5], onvalue=1, offvalue=0),
    tk.Checkbutton(root, text='D7', variable=checkboxValues[6], onvalue=1, offvalue=0),
    tk.Checkbutton(root, text='D8', variable=checkboxValues[7], onvalue=1, offvalue=0)
]

### PACK ###
scrollbar.pack(side="right", fill="y")
LBMessages.pack(side="left",fill="y")
btnSnapshot.pack(side="top", padx=1, pady=10)
btnClearFilters.pack(side="top", padx=1, pady=20)
btnMore.pack(side="top", padx=1, pady=5)
btnUnchanged.pack(side="top", padx=1, pady=5)
btnLess.pack(side="top", padx=1, pady=5)

for flt in rbFilters:
    flt.pack(side="top", padx=1, pady=5)

for chk in chkBoxes:
    chk.pack(side="top", padx=1, pady=2)


### SERIAL ###
ser = serial.Serial('COM13', 500000, timeout=1)
time.sleep(2)

### THREADS ###
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
