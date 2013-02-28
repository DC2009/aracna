#! /usr/bin/env python

#Notes: I'm going to want to make a new RunManager for Rex


import os
import math
from math import *
from datetime import *
from time import sleep
from types import FunctionType
from numpy import array, interp


from ax12 import *
from driver import Driver

#from RobotQuadratot import *
from Robot import Robot
from ConstantsRex import *


def lInterp(time, theDomain, val1, val2):
    ret = []
    for ii in range(len(val1)):
        ret.append(interp([time], theDomain, [val1[ii], val2[ii]])[0])
    return ret
    
class RobotFailure(Exception):
    pass

#class RobotRex(RobotQuadratot):
class RobotRex(Robot):
    ''''''

    def __init__(self, nServos, portName="", cmdRate=40):
        '''Initialize the robot.
        
        Keyword arguments:

        silentNetworkFail -- Whether or not to fail silently if the
                             network does not find all the dynamixel
                             servos.

        nServos -- How many servos are connected to the robot,
                   i.e. how many to expect to find on the network.

        commandRate -- Rate at which the motors should be commanded,
                   in Hertz.  Default: 40.
        '''
        
        #RobotQuadratot.__init__(self, commandRate=cmdRate, skipInit=True)
        Robot.__init__(self, commandRate=cmdRate, skipInit=True)
        self.commandsSent = 0
        self.nServos = nServos
        
        #Find a valid port.
        if os.name == "posix":
            possibilities = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/cu.usbserial-A800KDV8']
            for pos in possibilities:
                if os.path.exists(pos):
                    portName = pos
            if portName is None:
                raise Exception('Could not find any of %s' % repr(possibilities))
            self.port = Driver(portName, 38400, True)
        else:
            if portName is None:
                portName = 'COM6'
            self.port = Driver(portName, 38400, True)
            #self.port = None
        
#        if self.port is None:
#            raise Exception("Failed  to open any Serial/COM port")

        self.currentPos = None
        self.resetClock()
        
        self.loud = False

    '''REWRITE IF DESIRED'''
    def readyPosition(self, persist = False):
        if persist:
            self.resetClock()
            while self.time < 2.0:
                self.commandPosition(POS_READY)
                sleep(.1)
                self.updateClock()
        else:
            self.commandPosition(POS_READY)
            sleep(2)
    
    def __extract(self, li):
        """ extract x%256,x>>8 for every x in li """
        out = list()
        for i in li:
            ii = int(i)
            out = out + [ii%256,ii>>8]
        return out
        
    def interpMove(self, start, end, seconds,logFile=None, extraLogInfoFn=None):
        '''Performs the same function as interpMove() in RobotQuadratot but uses
        the new interface that I wrote up for Aracna.
            start -- a postion vector/function
            end -- a position vector/function
            seconds -- the duration the two functions should be interpolated over'''
        self.updateClock()
        
        timeStart = self.time
        timeEnd   = self.time + seconds
        
        print timeStart
        print timeEnd

        while self.time < timeEnd:
            #print 'time:', self.time
            self.updateClock()
            posS = start(self.time) if isinstance(start, FunctionType) else start
            posE =   end(self.time) if isinstance(end,   FunctionType) else end
            goal = lInterp(self.time, [timeStart, timeEnd], posS, posE)
            
            #print goal
            
            #write out the command to the robot
            self.commandOverTime(goal, int(self.sleep * 1000))
    
    def run(self, motionFunction, runSeconds = 10, resetFirst = True,
            interpBegin = 0, interpEnd = 0, timeScale = 1, logFile = None,
            extraLogInfoFn = None):
        '''Run the robot with a given motion generating function.

        Positional arguments:
        
        motionFunction -- Function used to generate the desired motor
                          positions.  This function must take a single
                          argument -- time, in seconds -- and must
                          return the desired length 9 vector of motor
                          positions.  The current implementation
                          expects that this function will be
                          deterministic.
        
        Keyword arguments:

        runSeconds -- How many seconds to run for.  This is in
                      addition to the time added for interpBegin and
                      interpEnd, if any.  Default: 10

        resetFirst -- Begin each run by resetting the robot to its
                      base position, currently implemented as a
                      transition from CURRENT -> POS_FLAT ->
                      POS_READY.  Default: True

        interpBegin -- Number of seconds over which to interpolate
                      from current position to commanded positions.
                      If this is not None, the robot will spend the
                      first interpBegin seconds interpolating from its
                      current position to that specified by
                      motionFunction.  This should probably be used
                      for motion models which do not return POS_READY
                      at time 0.  Affected by timeScale. Default: None

        interpEnd -- Same as interpBegin, but at the end of motion.
                      If interpEnd is not None, interpolation is
                      performed from final commanded position to
                      POS_READY, over the given number of
                      seconds. Affected by timeScale.  Default: None
                      
        timeScale -- Factor by which time should be scaled during this
                      run, higher is slower. Default: 1
                      
        logFile -- File to log time/positions to, should already be
                      opened. Default: None

        extraLogInfoFn -- Function to call and append info to every
                      line the log file. Should return a
                      string. Default: None
        '''

        #net, actuators = initialize()

        #def run(self, motionFunction, runSeconds = 10, resetFirst = True
        #    interpBegin = 0, interpEnd = 0):
        
        if self.loud:
            print 'Starting motion.'

        self.resetClock()
        
        print "About to call query()"
        self.currentPos = self.query()

        if logFile:
            #print >>logFile, '# time, servo goal positions (9), servo actual positions (9), robot location (x, y, age)'
            print >>logFile, '# time, servo goal positions (9), robot location (x, y, age)'

        # Reset the robot position, if desired
        if resetFirst:
            self.interpMove(self.query(), POS_FLAT, 3)
            self.interpMove(POS_FLAT, POS_READY, 3)
            #self.interpMove(POS_READY, POS_HALFSTAND, 4)
            self.currentPos = POS_READY
            self.resetClock()

        # Begin with a segment smoothly interpolated between the
        # current position and the motion model.
        if interpBegin is not None:
            self.interpMove(self.currentPos,
                            scaleTime(motionFunction, timeScale),
                            interpBegin * timeScale,
                            logFile, extraLogInfoFn)
            self.currentPos = motionFunction(self.time)

        # Main motion segment
        self.interpMove(scaleTime(motionFunction, timeScale),
                        scaleTime(motionFunction, timeScale),
                        runSeconds * timeScale,
                        logFile, extraLogInfoFn)
        self.currentPos = motionFunction(self.time)

        # End with a segment smoothly interpolated between the
        # motion model and a ready position.
        if interpEnd is not None:
            self.interpMove(scaleTime(motionFunction, timeScale),
                            POS_READY,
                            interpEnd * timeScale,
                            logFile, extraLogInfoFn)
            
    def commandOverTime(self, pos, dur):
        '''Writes out a packet to the robot to execute the commandOverTime
        function. Stalls after the command is sent to prevent overflowing the
        buffer on the robot.
            pos -- a position vector. Values are in the range [0,270]
            dur -- the duration (in milliseconds) of the transition'''
        dur1 = dur >> 8
        dur2 = dur & 0x00ff
        
        posArr = [0] * (self.nServos * 2)
        for i in range(self.nServos):
            posArr[2 * i] = int(pos[i]) >> 8
            posArr[2*i+1] = int(pos[i]) & 0x00ff
        
        startTime = datetime.now()
        
        #print "sending command" + str(datetime.now())
        newPos = self.port.execute2(COMMAND_OVER_TIME, [dur1, dur2] + posArr)
        
        #Calculate the real position vector and print it out
        if newPos is not None:
            realPos = [0] * 8
            for i in range(self.nServos): realPos[i] = (newPos[i*2] << 8) + (newPos[i*2+1])
            print realPos
        
        endTime = startTime + timedelta(0,self.sleep)
        while datetime.now() < endTime: sleep(self.sleep/20)
    
    def relax(self):
        '''Relaxes servos. Use when we are done with a motion sequence.'''
        for servo in range(self.nServos):
            self.port.setReg(servo+1,P_TORQUE_ENABLE, [0,])
    
    def commandPosition(self, position, crop = True, cropWarning = False):
        '''Simulates commandPosition using a "fake" function. The move will take 1 second. This is a hack.'''
        f = lambda t: position
        self.interpMove(f,f,1)

if __name__ == "__main__":
    robot = RobotRex(8, "COM7", cmdRate = 14)
    pi = math.pi
    
    dur = 100.0
    
    f1 = lambda t: (abs(270.0*sin(10*pi*t/dur)),abs(270.0*sin(10*pi*t/dur)),
                    abs(270.0*sin(10*pi*t/dur)),abs(270.0*sin(10*pi*t/dur)),
                    abs(270.0*sin(10*pi*t/dur)),abs(270.0*sin(10*pi*t/dur)),
                    abs(270.0*sin(10*pi*t/dur)),abs(270.0*sin(10*pi*t/dur)))
    f2 = lambda t: (abs(270.0*sin(3 *pi*t/dur)),abs(270.0*sin(10*pi*t/dur)),
                    abs(20.0*sin(1 *pi*t/dur)), abs(100.0*sin(10*pi*t/dur)),
                    abs(270.0*sin(10*pi*t/dur)),abs(270.0*sin(10*pi*t/dur)),
                    abs(270.0*sin(10*pi*t/dur)),abs(270.0*sin(10*pi*t/dur)))
    sleep(2)

    robot.interpMove(f1,f2,dur)