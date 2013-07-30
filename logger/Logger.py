import threading
import wx
import logging
from StringIO import StringIO
import HTMLParser
import os
import time
import subprocess
import sys

class Logger():

    def __init__(self, name):
        pass

    def sendLogMessagesToDebugWindowTextControl(self, logTextCtrl):
        pass

    def configureLogger(self):
        pass

    def debug(self, message):
        pass

    def error(self, message):
        pass

    def warning(self, message):
        pass

    def dump_log(self, launcherMainFrame, submit_log=False):
        pass

logger = Logger("launcher")


