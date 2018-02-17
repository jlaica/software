#!/usr/bin/python3

""" Main application for smartbench project """
'''
To run the server

    bokeh serve WebApp.py

Then navigate to the URL

    http://localhost:5006/WebApp

in your browser.

'''

#from pyftdi.ftdi import Ftdi
import serial
import time

import numpy as np

from bokeh.io import curdoc
from bokeh.layouts import row, widgetbox
from bokeh.models import ColumnDataSource, Range1d
from bokeh.models.layouts import Spacer
from bokeh.models.widgets import Slider, TextInput
from bokeh.plotting import figure
from bokeh.palettes import Viridis3

from tornado import gen
import tornado

from OscopeApi import *
#from SmartbenchAppLayout import *
#from ScopeStatus import *
from Configuration_Definitions import *

# Useful line:
# yield tornado.gen.sleep(1)

# callbacks
# https://bokeh.pydata.org/en/latest/docs/reference/server/callbacks.html
# https://bokeh.pydata.org/en/latest/docs/reference/document.html#bokeh.document.document.Document

_STATUS_STOPPED = 0
_STATUS_RUNNING = 1

_CHANNEL_ON     = 1
_CHANNEL_OFF    = 0

class SmartbenchApp():
    #global source_chA, source_chB, doc, plot

    def __init__(self, doc, plot, source_chA, source_chB):

        self.doc = doc
        self.plot = plot
        self.source_chA = source_chA
        self.source_chB = source_chB

        # Initializing oscope api
        self.smartbench = Smartbench()

        if(self.smartbench.isOpen()):

            # Default configuration
            self.configureScope()

            # This starts the application flow
            self.status = _STATUS_RUNNING

            # Plot axes
            self.plot.x_range = Range1d(0,self.smartbench.get_number_of_samples()-1)
            self.plot.y_range = Range1d(0,255)

            # Callback to start the acqusition, called as soon as possible
            self.doc.add_next_tick_callback(self.newFrameCallback)
        else:
            print("Device not connected!")
            exit()

        return

    def statusChanged(self, status):
        if(status == _STATUS_RUNNING):
            self.stop()
        else:
            self.start()
        return

    def start(self):
        self.status = _STATUS_RUNNING
        self.doc.add_next_tick_callback(self.newFrameCallback)
        return

    def stop(self):
        self.status = _STATUS_STOPPED

        #Clock.unschedule(self.waitingTriggerCallback)
        try:    remove_timeout_callback(self.waitingTriggerCallback)
        except: pass
        #Clock.unschedule(self.newFrameCallback)
        try:    remove_next_tick_callback(self.newFrameCallback)
        except: pass

        return
    # --------------------------------------------------------
    # This method sends a "Start Request" to the device.
    @gen.coroutine
    def newFrameCallback(self):
        self.triggered      = 0
        self.buffer_full    = 0
        self.count          = 0
        print("> Request Start")
        self.smartbench.request_start()
        self.doc.add_next_tick_callback(self.waitingTriggerCallback) # Called as soon as possible
        return

    # --------------------------------------------------------
    # This method will query the trigger status and the buffer status, which could
    # be {Triggered / Not triggered} and { buffer full / buffer not full } respectively.
    # Depending on the status, and the mode of operation (Normal or Auto) will wait or
    # not to show the data.
    @gen.coroutine
    def waitingTriggerCallback(self):
        print("> Request Trigger Status")
        self.smartbench.request_trigger_status()
        print("> Waiting...")
        self.buffer_full,self.triggered = self.smartbench.receive_trigger_status()
        print("> Trigger={}\tBuffer_full={}".format( self.triggered, self.buffer_full ))

        if self.triggered==0 or self.buffer_full==0:
            if( self.smartbench.is_trigger_mode_single() or self.smartbench.is_trigger_mode_normal() ):
                self.doc.add_timeout_callback(self.waitingTriggerCallback,100) # Check again in 100 ms.
                return
            else:
                if(self.buffer_full == 1 and self.count < 5):
                    self.count = self.count + 1
                    self.doc.add_timeout_callback(self.waitingTriggerCallback,100) # Check again in 100 ms.
                    return

        # First, stops the capturing.
        print("> Request Stop")
        self.smartbench.request_stop()

        # If channel is ON, requests the data.
        if(self.smartbench.get_chA_status() == _CHANNEL_ON):
            print("> Request CHA")
            self.smartbench.request_chA()

            print("> Waiting...")
            self.dataY_chA = list(reversed(self.smartbench.receive_channel_data()))
            self.dataX_chA = range(0,len(self.dataY_chA))
        else:
            self.dataY_chA = []
            self.dataX_chA = []

        # If channel is ON, requests the data.
        if(self.smartbench.get_chB_status() == _CHANNEL_ON):
            # Then, requests the data.
            print("> Request CHB")
            self.smartbench.request_chB()

            print("> Waiting...")
            self.dataY_chB = list(reversed(self.smartbench.receive_channel_data()))
            self.dataX_chB = range(0,len(self.dataY_chB))
        else:
            self.dataY_chB = []
            self.dataX_chB = []


        self.source_chA.data = dict(x=self.dataX_chA, y=self.dataY_chA)
        self.source_chB.data = dict(x=self.dataX_chB, y=self.dataY_chB)

        if( self.smartbench.is_trigger_mode_auto() or self.smartbench.is_trigger_mode_normal() ):
            if(self.status == _STATUS_RUNNING):
                self.doc.add_next_tick_callback(self.newFrameCallback ) # Called as soon as possible

        return


    def configureScope(self):
        self.smartbench.setDefaultConfiguration()

        # # For a good visualization with "Fake_ADC", clk divisor must be 1.
        # # ADC CLOCK SET TO 20MHz
        # self.smartbench.chA.set_clk_divisor(Configuration_Definitions.Clock_Adc_Div_Sel[13])
        # self.smartbench.chB.set_clk_divisor(Configuration_Definitions.Clock_Adc_Div_Sel[13]) # not necessary, ignored
        # # AVERAGE DISABLED (1 SAMPLE)
        self.smartbench.chA.set_nprom(Configuration_Definitions.Mov_Ave_Sel[13])
        self.smartbench.chB.set_nprom(Configuration_Definitions.Mov_Ave_Sel[13])

        return


if __name__ == '__main__':
    try:
        sm = SmartbenchApp()
        #sm.run()
    except KeyboardInterrupt:
        print ("Interrupted")
        sm.smartbench.oscope.close()
        exit()
