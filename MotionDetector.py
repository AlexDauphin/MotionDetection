#!/usr/bin/python
import os, sys, stat
import cv2
import urllib
import numpy as np
import time
from StringIO import StringIO
from PIL import Image                                                                                                                                                         
# remotemotion.py 
# Copyright 2015, Ron Ostafichuk                                                                                                                         
# MIT License (you are free to use it for anything)                                                                                                                                            
                                                                                                                                                         
# This is a Python program to read mjpg-streamed data from multiple                                                                                      
# raspberry pi or odroid or commercial web cameras that support MJPEG streaming                                                                                                       
# and run a motion detection algorithm to                                                                                              
# decide what frames to save to the hard drive
# organize the saved images by day by creating directories for each day
# save the single largest diff image to a summary directory for easy review

                                                                                                           
# differential image function
def diffImg(t0, t1):
  d = cv2.absdiff(t1, t0)
  return d


# make direcotry if it does note exist
def makeDirectory( d ):
    if not os.path.exists(d) :
        print("Making Directory " + d )
        os.makedirs(d)
        # set the directory to be read write for anyone!
        fd = os.open( d, os.O_RDONLY )
        os.fchmod(fd,stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IWUSR | stat.S_IRUSR | stat.S_IWGRP | stat.S_IRGRP | stat.S_IWOTH | stat.S_IROTH)
        os.close(fd)
    return

def saveImage(fileName,image) :
    try:
        # save image
        cv2.imwrite(fileName,image)
        # make sure anyone can read and write this image if running as root
        fd = os.open( fileName, os.O_RDONLY )
        os.fchmod(fd,stat.S_IWUSR | stat.S_IRUSR | stat.S_IWGRP | stat.S_IRGRP | stat.S_IWOTH | stat.S_IROTH)
        os.close(fd)
    except:
        print("Error saving image")
    return




class MotionStream:
    tsLastOpen = 0
    sURL = '' # url for connection to mjpg stream
    sSubDirectory = '' # each camera can have it's own subdirectory for images
    stream = None
    aRawBytes = ''    
    image1=None
    image2=None
    summaryImage = None # use this to keep the image with the largest diff for the summary folder    
    nSummaryDiff = 0 # diff for this summary image 
    summaryFileName = ''
    
    nFrame = 0 # frame number
    nFrameInEvent = 0 # frame number for a specific motion event
    timeForStartOfEvent = time.time() 
    
    dAvgDiff = 4000000
    aDiff = [] # use a frame diff average for the trigger
        
    nCnt = 0 # count of images used for building average
    
    def __init__(self, sURL, sSubDir):
        #init the member variables
        self.sURL = sURL
        self.sSubDirectory = ''
        if len(sSubDir) > 0 :
            self.sSubDirectory = '/' + sSubDir # make sure subdirectory has leading slash for later
            
        for i in range(gnWindowSize):
            self.aDiff.append(0) # init diff window

        self.open() # try to open right away
    
    def open(self):
        # Open stream from url
        # record last open attempt so we do not try to reopen too often
        self.tsLastOpen = time.time() 
        try:
            self.stream = urllib.urlopen(self.sURL)
            print("Opened " + self.sURL )
        except:
            print("Error: Could not open " + self.sURL )
            self.stream = None
            
    def readAndProcess(self):
        # check if stream is open, if not then try to open it
        if self.stream is None:
            # try to re-open stream every 10 seconds forever
            if time.time() - self.tsLastOpen > 10:
                self.open()
            return
        
        # read from stream
        nSize = len(self.aRawBytes)
        if self.stream is not None:
            self.aRawBytes += self.stream.read(1024)
        nBytesRead= len(self.aRawBytes) - nSize
        if nBytesRead == 0 and self.stream is not None:
            print(self.sURL + " Lost Connection")
            self.stream.close()
            self.stream = None
            return
            
        # process stream
        if nBytesRead ==0 and nSize > 0 :
            # no data, end of stream?
            print("No data for stream " + str(i) )
            aBytes = '' # clear stream to stop messages
        if nBytesRead > 0 :
            # print("Read " + str(nBytesRead) + " bytes")
                                                                                                                                                         
            a = self.aRawBytes.find('\xff\xd8') #find start of image
            b = self.aRawBytes.find('\xff\xd9') #find end of image
            if a!=-1 and b!=-1:
                # found an image in the stream
                timeNow = time.time()
                jpg = self.aRawBytes[a:b+2]
                self.aRawBytes = self.aRawBytes[b+2:]

                # in order to stop the Corrupt JPEG data: 1 extraneous bytes before marker 0xd9 error from cv2 without
                # Recompiling the cv2 module
                # do some re-encoding with pil to ensure a cv2 accepted JPEG format
                stream_as_string_io = StringIO(jpg)
                stream_as_pil = Image.open(stream_as_string_io)
                output_string = StringIO()
                stream_as_pil.save(output_string, format="JPEG")
                new_jpeg_stream = output_string.getvalue()
                output_string.close()
                stream_as_string_io.close()
                jpg = new_jpeg_stream


                # read next image
                self.image1 = self.image2
                imageClr = cv2.imdecode(np.fromstring(jpg,dtype=np.uint8),cv2.IMREAD_COLOR)
		self.image2 = cv2.cvtColor(imageClr, cv2.COLOR_RGB2GRAY) # convert to grey for diffs
                self.nFrame += 1
                if not (self.image1 is None or self.image2 is None ) :
                    # two valid images exist, so we can start comparing them
                    diff = diffImg(self.image1,self.image2).sum()
                    self.aDiff[self.nFrame] = diff
                    if self.nFrame % 10 == 0 :
                        #update the average every 10 frames and output a status
                        newAvgSum = self.dAvgDiff*10
                        nItemsInSum = 0
                        for e in self.aDiff :
                            if e > 1 :
                                newAvgSum += e
                                nItemsInSum+=1
                        self.dAvgDiff = int(newAvgSum / (nItemsInSum+10)) # new average has 1% weighting from previous avg once buffer is full
                        print(self.sURL + " Image (" + str(self.nFrame) + ") size=" + str(len(jpg)) +" , Diff= "+str(diff) + " , dAvgDiff=" + str(self.dAvgDiff))

                    if self.nFrame >= gnWindowSize -1 :
                        self.nFrame = 0 #start filling array from the start again
    
                    if diff > self.dAvgDiff*gdThreshold : # % above average
                        # found large enough difference, save it
                        
                        if timeNow - self.timeForStartOfEvent < 10 :
                            # still in same event                        
                            self.nFrameInEvent += 1
                            #update start time so we stay in the event until 10 seconds elapse without a saved frame
                            self.timeForStartOfEvent = timeNow
                        else:
                            # close last event, and start a new one                            
                            print("New Event " + time.strftime("%Y%m%d %H:%M:%S",time.localtime()))
                            if len(self.summaryFileName) > 0 :
                                # save last summary image (AS LONG AS THERE ARE AT LEAST 4 Frames in the event!)                                
                                if self.nFrameInEvent > 3 :
                                    print("Saving Summary " + self.summaryFileName)
                                    saveImage(self.summaryFileName,self.summaryImage)
                                # clear vars in preparation for new event
                                self.summaryImage = None
                                self.summaryFileName = ''
                                self.nSummaryDiff = 0
                            self.nFrameInEvent = 1
                            self.timeForStartOfEvent = timeNow
                                
                        
                        if diff > self.nSummaryDiff :
                            # found new better summary image
                            self.nSummaryDiff = diff
                            self.summaryImage = imageClr
                            self.summaryFileName = gPathForSummary + time.strftime("/%Y%m%d-%H%M%S-",time.localtime()) + str(self.nFrameInEvent) + ".jpg"
                            
                        # make sure directory exists for todays date
                        d = gPathForImages + self.sSubDirectory + time.strftime("/%Y%m%d",time.localtime())
                        makeDirectory(d)
                    
                        # save image to drive
                        fileName = gPathForImages + self.sSubDirectory + time.strftime("/%Y%m%d/%Y%m%d-%H%M%S-",time.localtime()) + str(self.nFrameInEvent) + ".jpg"   
                        print("Saving " + fileName + ", Diff=" + str(diff) + ", dAvgDiff=" + str(self.dAvgDiff))
                        saveImage(fileName,imageClr)



# Main program begins here
# global settings
gPathForImages = "/home/pi/RaspMotionDetection/motion"
gPathForSummary = "/home/pi/RaspMotionDetection/motion/summary" # location used to store single image per event
gdThreshold = 1.30 # Detect motion at 30% above average diff
gnWindowSize = 500 # home many frames to include in the difference average

gaMotionStream = []
# open all your URL streams here by adding new lines with the proper URLs 
gaMotionStream.append(MotionStream('http://192.168.0.154:8080/?action=stream','driveway'))
#MotionStream.append(MotionStream('http://192.168.1.53:8080/?action=stream','subdir_name'))

print("===============================================")
print("remotemotion.py Remote Motion Detection program")
print(" ")
print("Licensed under the MIT license by Ron Ostafichuk")
print(" ")
print("Detecting at " + str((gdThreshold-1)*100) + "% above avg noise threshold ")
print("Using " + str(gnWindowSize) + " frames for averages")
print("Saving to " + gPathForImages)
print(" ")

# make sure file directory exists
makeDirectory(gPathForImages)
makeDirectory(gPathForSummary)    

# main loop to read and process the streams
while True:
    for motionStream in gaMotionStream:
        motionStream.readAndProcess()

# end
