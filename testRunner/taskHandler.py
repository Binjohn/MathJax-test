# -*- Mode: Python; tab-width: 2; indent-tabs-mode:nil; -*-
# vim: set ts=2 et sw=2 tw=80:
# ***** BEGIN LICENSE BLOCK *****
# Version: Apache License 2.0
#
# Copyright (c) 2011 Design Science, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contributor(s):
#   Frederic Wang <fred.wang@free.fr> (original author)
#
# ***** END LICENSE BLOCK *****

"""
@file taskHandler.py
The file for the @ref taskHandler module.

@package taskHandler
This module implements a server handling a task list. It can communicate
with external programs such that Web server to receive instructions or provides
the current status of each task. It also runs and communicates task programs
(which are testing instance executing the runTestsuite.py script) so that it
knows the status and progress of each running task.

@var gServer
The server handling the task list.

@var TASK_LIST_DIRECTORY
Path to the taskList directory
"""

from config import PYTHON
from config import TASK_HANDLER_HOST, TASK_HANDLER_PORT
from config import HOST_LIST, DEFAULT_SELENIUM_PORT
from config import DEFAULT_MATHJAX_PATH, DEFAULT_MATHJAX_TEST_PATH 
from config import DEFAULT_TIMEOUT
from config import MONTH_LIST, WEEKDAY_LIST

TASK_LIST_DIRECTORY = "config/taskList/"
TASK_LIST_TXT = "taskList.txt"
MATHJAX_WEB_PATH = "../web/"

from crontab import CronTab
from datetime import datetime, timedelta
from signal import SIGINT
import ConfigParser
import SocketServer
import collections
import os
import socket
import subprocess

def boolToString(aBoolean):
    """
    @fn boolToString(aBoolean)
    @brief A simple function to convert a boolean to a string

    @return the string "true" or "false"
    """
    if aBoolean:
        return "true"
    return "false"

def getDirectoryFromDate():
    """
    @fn getDirectoryFromDate()
    @brief generate a directory name from the current date of the day

    @return "YEAR-MONTH-DATE/"
    """
    return datetime.utcnow().strftime("%Y-%m-%d/")

class requestHandler(SocketServer.StreamRequestHandler):
    """
    @class taskHandler::requestHandler
    @brief A class inheriting from SocketServer.StreamRequestHandler and dealing
    with the requests received by the task handler.
    """

    def readExceptionMessage(self):
        """
        @fn readExceptionMessage(self)
        @brief read an exception message
        @return The exception message read from the socket

        This function reads line from the socket and concatenated them in a
        string until it reaches a "TASK DEATH END" line.
        """

        s = ""

        while (True):
            request = self.rfile.readline().strip()
            if (request == "TASK DEATH END"):
                break
            s += request + "\n"

        return s

    def addTask(self, aTaskName, aConfigFile, aOutputDirectory, aSchedule):
        """
        @fn addTask(self, aTaskName, aConfigFile, aOutputDirectory, aSchedule)
        @brief add a new item to the task list
        @param aTaskName name of the task
        @param aConfigFile configuration file to use. If it is None, the
        config parameters will be read from the socket.
        @param aOutputDirectory directory to store results of the task. If it
        is None, the task name is used instead.
        @param aSchedule @ref taskHandler::task::mSchedule of the task
        @return a message indicating whether the task has been successfully
        added or not.

        If the task with the same name is not already in the task list,
        this function creates a new task with the specified name, a status
        "Inactive". The output directory is of the form DATE/aOutputDirectory.
        Task configuration are read from the socket and stored in the
        task::mParameters table of the task.
        """

        global gServer

        if aTaskName in gServer.mTasks.keys():
            return "'" + aTaskName + "' is already in the task list!" + "'\n"

        # create a new task
        if aOutputDirectory == None:
            aOutputDirectory = aTaskName

        if aSchedule == None:
            # if the task is not scheduled, store the results in a directory
            # with the date of the day
            aOutputDirectory = getDirectoryFromDate() + aOutputDirectory

        t = task(aTaskName, "Inactive", aOutputDirectory + "/", aSchedule)

        # read the configuration parameters of the task
        if aConfigFile == None:
            t.readParametersFromSocket(self)
        else:
            if (not os.path.exists(aConfigFile)):
                return "File '" + aConfigFile + "' not found."
            t.readParametersFromConfigFile(aConfigFile)

        # add the task to the list
        gServer.mTasks[aTaskName] = t
        t.generateConfigFile()

        if t.mSchedule != None:
            # add the task to the scheduler
            gServer.addScheduledTask(t)

        return "'" + aTaskName + "' added to the task list.\n"

    def removeTask(self, aTaskName):
        """
        @fn removeTask(self, aTaskName)
        @brief remove an item from the task list
        @param aTaskName name of the task to remove
        @return a message indicating whether the task has been successfully
        removed or not.

        The task is removed only if the task is in the list and not running.
        """
        global gServer

        if aTaskName not in gServer.mTasks.keys():
            return "'" + aTaskName + "' was not found in the task list!"

        t = gServer.mTasks[aTaskName]
        if (not t.isRunning()):
            if t.mSchedule != None:
                # remove the task from the scheduler
                gServer.removeScheduledTask(t)

            # remove the task from the list
            t.removeConfigFile()
            del gServer.mTasks[aTaskName]
            return "'" + aTaskName + "' removed from the task list.\n"
       
        return "'" + aTaskName + "' is running and can not be removed!\n"

    def runTask(self, aTaskName, aRestart = False):
        """
        @fn runTask(self, aTaskName, aRestart = False)
        @brief launch the execution of a task or put it in the pending queue.
        @param aTaskName name of the task to run
        @param aRestart Whether we should run the task from the beginning or
        continue it if it was interrupted
        @return a message indicating the result of this action.
        """

        global gServer

        if aTaskName not in gServer.mTasks.keys():
            return "'" + aTaskName + "' was not found in the task list!"

        t = gServer.mTasks[aTaskName]

        if (t.isRunning()):
            return "'" + aTaskName + "' is already running!\n"

        if (aRestart):
            t.mParameters["startID"] = ""

        h = t.host()
        if (h in gServer.mRunningTasksFromHost.keys()):
            # Tasks are already running on this host: verify the status.
            # This may change the list of running/pending tasks!
            gServer.verifyHostStatus(h)
            if (t.isRunning()):
                return "'" + aTaskName + "' is already running!\n"

        if (t.isPending()):
            return "'" + aTaskName + "' is already pending!\n"

        gServer.addTaskToPendingQueue(t)
        gServer.runNextTasksFromPendingQueue(h)

        return "'" + aTaskName + "' added to the pending queue.\n"

    def stopTask(self, aTaskName):
        """
        @fn stopTask(self, aTaskName)
        @brief stop the execution of a task
        @return a message indicating whether the task has been successfully
        stopped or not.

        The task can be stopped if it is in the task list and running. In that
        case a SIGINT signal is sent to the corresponding testing instance
        process.
        """

        global gServer

        if aTaskName not in gServer.mTasks.keys():
            return "'" + aTaskName + "' was not found in the task list!"

        t = gServer.mTasks[aTaskName]

        if (t.isRunning()):
            t.mPopen.send_signal(SIGINT)
            return "Stop signal sent to '" + aTaskName + "'.\n"

        return "'" + aTaskName + "' is not running!\n"

    def handle(self):
        """
        @fn handle(self)
        @brief Handle a client request

        For security reasons, this function only accept request from clients on
        localhost (127.0.0.1). It reads a line from the socket and sends a
        response:

        - If the request is "TASKVIEWER", it sends the result of
        @ref taskHandler::getTaskList

        - If the request is "TASKINFO taskName", it send the result of
        @ref taskHandler::getTaskInfo for the corresponding task.

        - If the request is "TASK UPDATE pid status progress", where pid the PID
        of the process of a running task, it updates the members of the given
        task accordingly. If status is "Interrupted", progress is actually the
        startID to use to recover the testing instance.
        In particular, it can be ommited if the task was interrupted before
        any tests have been run (i.e. startID should be an empty string).

        - If the request is "TASK *_DEATH pid" where * is either
          "EXPECTED" or "UNEXPECTED" and pid the PID of the process of a running
          task, then that task is removed from the hash tables of running tasks.
          If the death is unexpected, the @ref task::mStatus is set to
          "Killed" and @ref task::mExceptionMessage is read using
          @ref readExceptionMessage.

        - If the request starts by "TASKEDITOR command taskName", then it
        performs one of the following command and returns the information
        message:
            - "TASKEDITOR ADD taskName configFile outputDirectory": @ref addTask
            - "TASKEDITOR REMOVE taskName": @ref removeTask
            - "TASKEDITOR RUN taskName": @ref runTask with aRestart = False
            - "TASKEDITOR RESTART taskName": @ref runTask with aRestart = True
            - "TASKEDITOR STOP taskName": @ref stopTask

        - other requests are ignored.
        """

        global gServer

        if (self.client_address[0] == "127.0.0.1"):
            # Only accept request from localhost
            request = self.rfile.readline().strip()
            print request
            items = request.split()
            client = items[0]
            if (client == "TASKVIEWER"):
                self.wfile.write(gServer.getTaskList())
            elif (client == "TASKINFO"):
                taskName = items[1]
                self.wfile.write(gServer.getTaskInfo(taskName))
            elif (client == "TASK"):
                command = items[1]
                pid = items[2]
                if pid in gServer.mRunningTaskFromPID.keys():
                    t = gServer.mRunningTaskFromPID[pid]
                    if (command == "UPDATE"):
                        status = items[3]
                        if (status in
                            ["Running", "Complete", "Interrupted"]):
                            t.mStatus = status
                            if (t.mStatus == "Interrupted"):
                                if (len(items) >= 5):
                                    t.mParameters["startID"] = items[4]
                                else:
                                    t.mParameters["startID"] = ""
                            else:
                                t.mProgress = items[4]
                    elif (command == "EXPECTED_DEATH" or
                          command == "UNEXPECTED_DEATH"):
                        del gServer.mRunningTaskFromPID[pid]
                        gServer.removeTaskFromRunningList(t)
                        if (command == "UNEXPECTED_DEATH"):
                            t.mStatus = "Killed"
                            t.mExceptionMessage = self.readExceptionMessage()
                        gServer.runNextTasksFromPendingQueue(t.host())
                        
            elif (client == "TASKEDITOR"):
                command = items[1]
                taskName = items[2]
                if command == "ADD":
                    if items[3] == "None":
                        configFile = None
                    else:
                        configFile = items[3]
                    if items[4] == "None":
                        outputDirectory = None
                    else:
                        outputDirectory = items[4]
                    if items[5] == "None":
                        schedule = None
                    else:
                        schedule = items[5]
                    self.wfile.write(self.addTask(taskName,
                                                  configFile,
                                                  outputDirectory,
                                                  schedule))
                elif command == "REMOVE":
                    self.wfile.write(self.removeTask(taskName))
                elif command == "RUN":
                    self.wfile.write(self.runTask(taskName, False))
                elif command == "RESTART":
                    self.wfile.write(self.runTask(taskName, True))
                elif command == "STOP":
                    self.wfile.write(self.stopTask(taskName))
        else:
            print "Received request by unknown host " + self.client_address[0]

class task:
    """
    @class taskHandler::task
    @brief A class representing items in the task list.
    """

    def __init__(self, aName, aStatus, aOutputDirectory, aSchedule):
        """
        @fn __init__(self, aName, aStatus, aOutputDirectory, aSchedule)

        @param aName            Value to assign to @ref mName
        @param aStatus          Value to assign to @ref mStatus
        @param aOutputDirectory Value to assign to @ref mOutputDirectory
        @param aSchedule        Value to assign to @ref mSchedule

        @property mName
        Name of the task

        @property mStatus
        Status of the task:
          - Process not executed yet: "Inactive", "Scheduled"
          - Process waiting to execute: "Pending"
          - Process executing: "Running"
          - Process executed: "Complete", "Interrupted", "Killed"

        @property mOutputDirectory
        Directory where the results of the task are stored.

        @property mProgress
        Either "-" or a fraction "numberOfTestsExecuted/totalNumberOfTests".

        @property mParameters
        Hash table of task parameters, corresponding to those in the config
        file.
        @see ../html/components.html\#test-runner-config

        @property mPopen
        The result of the subprocess.Popen or None if the task was never
        executed.

        @property mExceptionMessage
        If the task has the "Killed" status, the Exception message raised by
        the task process before dying or "No exception raised" if the death was
        not reported. Otherwise, it is None.

        @property mSchedule
        If the task is scheduled, the string "m,h,dom,mon,dow" representing an
        entry in the crontab. Otherwise, it is None.

        This function initializes @ref mName, @ref mStatus and
        @ref mOutputDirectory with the given arguments ; @ref mProgress to "-",
        @ref mPopen and @ref mExceptionMessage to None ; @ref mParameters to an
        a hash table with a single "host" parameter with value None.
        """
        self.mName = aName
        self.mStatus = aStatus
        self.mProgress = "-"
        self.mParameters = {}
        self.mParameters["host"] = None
        self.mPopen = None
        self.mOutputDirectory = aOutputDirectory
        self.mExceptionMessage = None
        self.mSchedule = aSchedule

    def host(self):
        """
        @fn host(self)
        @brief get the IP address of a machine
        @return the host corresponding to @ref mParameters["host"] or "Unknown"
        this parameter is None.
        """
        h = self.mParameters["host"]
        if h != None:
            return socket.gethostbyname(h)
        else:
            return "Unknown"

    def isPending(self):
        """
        @fn isPending(self)
        """
        return (self.mStatus == "Pending")

    def isRunning(self):
        """
        @fn isRunning(self)
        @brief Indicate whether a task is running according to the value of
        @ref mPopen.
        @return Whether the task is running.
        """
        return (self.mPopen != None and self.mPopen.poll() == None)

    def aloneOnHost(self):
        """
        @fn aloneOnHost(self)
        @brief Indicate whether the task should run alone on the test machine
        @return self.mParameters["aloneOnHost"]
        """
        return self.mParameters["aloneOnHost"]

    def verifyStatus(self):
        """
        @fn verifyStatus(self)
        @brief Verify the consistency of the task @ref mStatus

        This function is intended to be used before providing the task status
        to the user. It verify that this status is consistent with the one
        provided by @ref isRunning.

        If the process is not running but @ref mStatus says it is, then we set
        the status to "Killed" and remove it from the task from the hash tables
        of running process. This may happen if the runTestsuite process died
        unexpectedly, without raising a BaseException.

        If the process is running but the @ref mStatus says "Inactive" or
        "Pending", set the status to "Running". This may happen if the
        runTestsuite did not send the "Running" status yet.
        """
        global gServer

        running = self.isRunning()

        if ((not running) and self.mStatus == "Running"):
            self.mStatus = "Killed"
            self.mExceptionMessage = "No exception raised"
            gServer.removeTaskFromRunningList(t)
            pid = str(self.mPopen.pid)
            if pid in gServer.mRunningTaskFromPID.keys():
                del gServer.mRunningTaskFromPID[pid]
            gServer.runNextTasksFromPendingQueue(t.host())
        elif (running and
              (self.mStatus == "Inactive" or
               self.mStatus == "Pending")):
            self.mStatus = "Running"

    def serialize(self):
        """
        @fn serialize(self)
        @brief Provide a short serialization of the task
        @return "host status progress outputDirectory"

        host, status, progress and outputDirectory correspond to the data
        members of the task.
        """
        self.verifyStatus()

        s = ""
        s += self.mParameters["host"] + " "
        s += self.mStatus + " ";
        s += self.mProgress + " "
        s += self.mOutputDirectory + " "
        if (self.mSchedule != None):
            s += self.mSchedule
        else:
            s += "None"

        return s

    def serializeMember(self, aName, aValue):
        """
        @fn serializeMember(self, aName, aValue)
        @brief serialize a pair (aName, aValue) as an HTML row
        @return an HTML row tr(th(aName), td(aValue)) in text format
        """
        return "<tr><th>" + aName + "</th><td>" + aValue + "</td></tr>"

    def serializeParameter(self, aKey):
        """
        @fn serializeParameter(self, aKey)
        @brief serialize a (aKey, @ref mParameters[aKey]) as an HTML row
        @return an HTML row tr(th(aKey), td(aValue)) in text format
        """
        return self.serializeMember(aKey, self.mParameters[aKey].__str__())

    def serializeSchedule(self, aSchedule):
        """
        @fn serializeSchedule(self, aSchedule)
        @brief serialize the date of scheduled task
        """
        items = aSchedule.split(",")
        date = ""

        if (items[4] == "*"):
            date += "******"
        else:
            date += WEEKDAY_LIST[int(items[4]) - 1]

        date += " "

        if (items[2] == "*"):
            date += "**"
        else:
            date += items[2]

        date += " "

        if (items[3] == "*"):
            date += "******"
        else:
            date += MONTH_LIST[int(items[3]) - 1]

        date += " ; "

        if (items[1] == "*"):
            date += "**"
        else:
            if (len(items[1]) == 1):
                # add a 0 if hours are < 10
                date += "0"
                date += items[1]
        date += ":"

        if (items[0] == "*"):
            date += "**"
        else:
            if (len(items[0]) == 1):
                # add a 0 if minutes are < 10
                date += "0"
                date += items[0]

        return self.serializeMember("Scheduled", date)

    def serializeHTML(self):
        """
        @fn serializeHTML(self)
        @brief Provide an HTML serialization of the task.
        @return string representation of HTML tables with the task info.
        """
        self.verifyStatus()

        s = ""

        s += "<h2>Task</h2>"
        s += "<p><table>"
        s += self.serializeMember("Name", self.mName)
        s += self.serializeMember("Status", self.mStatus)
        s += self.serializeMember("Progress", self.mProgress)

        s += "<tr><th>Result directory</th><td>"

        if (os.path.exists(MATHJAX_WEB_PATH + "results/" +
                           self.mOutputDirectory)):
            s += "<a href=\"results/" + self.mOutputDirectory + "\">"
            s += self.mOutputDirectory + "</a></td></tr>"
        else:
            s += self.mOutputDirectory

        if (self.mSchedule != None):
            s += self.serializeSchedule(self.mSchedule)

        if (self.mExceptionMessage != None):
            s += "<tr style=\"color: red;\">"
            s += "<th id='exceptionError'>Exception Error</th>"
            s += "<td>" + self.mExceptionMessage + "</td></tr>"

        s += "</table></p>"

        s += "<h2>Framework Configuration</h2>"
        s += "<p><table>"
        s += self.serializeParameter("host")
        s += self.serializeParameter("port")
        s += self.serializeParameter("mathJaxPath")
        s += self.serializeParameter("mathJaxTestPath")
        s += self.serializeParameter("timeOut")
        s += self.serializeParameter("useWebDriver")
        s += self.serializeParameter("fullScreenMode")
        s += self.serializeParameter("aloneOnHost")
        s += self.serializeParameter("formatOutput")
        s += self.serializeParameter("compressOutput")
        s += "</table></p>"
        
        s += "<h2>Platform Configuration</h2>"
        s += "<p><table>"
        s += self.serializeParameter("operatingSystem")
        s += self.serializeParameter("browser")
        s += self.serializeParameter("browserMode")
        s += self.serializeParameter("browserPath")
        s += self.serializeParameter("font")
        s += self.serializeParameter("nativeMathML")
        s += "</table></p>"

        s += "<h2>Testsuite Configuration</h2>"
        s += "<p><table>"
        s += self.serializeParameter("runSlowTests")
        s += self.serializeParameter("runSkipTests")
        s += self.serializeParameter("listOfTests")
        s += self.serializeParameter("startID")
        s += "</table></p>"

        return s

    def getConfigPath(self):
        """
        @fn getConfigPath(self)
        @brief Get a configuration path
        @return path to the configuration file for this task

        The path is the concatenation of "config/", the name of the task
        and the extension ".cfg".
        """
        return TASK_LIST_DIRECTORY + self.mName + ".cfg"

    def generateConfigFile(self):
        """
        @fn generateConfigFile(self)
        @brief generate a configuration file for this task

        This function creates a configuration file at the @ref getConfigPath
        path, with respect to the data members of the task.
        """
        p = self.mParameters;

        fp = file(self.getConfigPath(), "w")

        fp.write("[framework]\n")        
        fp.write("host = " + p["host"] + "\n")
        fp.write("port = " + str(p["port"]) + "\n")
        fp.write("mathJaxPath = " + p["mathJaxPath"] + "\n")
        fp.write("mathJaxTestPath = " + p["mathJaxTestPath"] + "\n")
        fp.write("timeOut = " + str(p["timeOut"]) + "\n")
        fp.write("useWebDriver = " + boolToString(p["useWebDriver"]) + "\n")
        fp.write("fullScreenMode = " + boolToString(p["fullScreenMode"]) + "\n")
        fp.write("aloneOnHost = " + boolToString(p["aloneOnHost"]) + "\n")
        fp.write("formatOutput = " + boolToString(p["formatOutput"]) + "\n")
        fp.write("compressOutput = " + boolToString(p["compressOutput"]) + "\n")
        fp.write("\n")

        fp.write("[platform]\n")
        fp.write("operatingSystem = " + p["operatingSystem"] + "\n")
        fp.write("browser = " + p["browser"] + "\n")
        fp.write("browserMode = " + p["browserMode"] + "\n")
        fp.write("browserPath = " + p["browserPath"] + "\n")
        fp.write("font = " + p["font"] + "\n")
        fp.write("nativeMathML = " + boolToString(p["nativeMathML"]) + "\n")
        fp.write("\n")

        fp.write("[testsuite]\n")
        fp.write("runSlowTests = " + boolToString(p["runSlowTests"]) + "\n")
        fp.write("runSkipTests = " + boolToString(p["runSkipTests"]) + "\n")
        fp.write("listOfTests = " + p["listOfTests"] + "\n")
        fp.write("startID = " + p["startID"] + "\n")

        fp.close()

    def removeConfigFile(self):
        """
        @fn removeConfigFile(self)
        @brief remove the configuration file for this task
        """
        os.remove(self.getConfigPath())

    def execute(self):
        """
        @fn execute(self)
        @brief Execute a new runTestsuite.py subprocess
        @return Python's subprocess.Popen instance representing the subprocess

        Call "python runTestsuite.py -c configName -o outputDirectory -t"
        where configName is the value returned by @ref getConfigPath and
        outputDirectory is @ref mOutputDirectory.
        """
        global gServer
        self.generateConfigFile()
        self.mExceptionMessage = None
        self.mPopen = subprocess.Popen([PYTHON, 'runTestsuite.py',
                                        '-c', self.getConfigPath(),
                                        '-o', self.mOutputDirectory,
                                        '-t'])
        gServer.mRunningTaskFromPID[str(self.mPopen.pid)] = self
        gServer.addTaskToRunningList(self)

    def setParameter(self, aParameterName, aParameterValue):
        """
        @fn setParameter(self, aParameterName, aParameterValue)
        @param aParameterName name of the parameter
        @param aParameterValue value of the parameter
        @see ../html/components.html\#test-runner-config
        @note multiple option values and unknown parameters are rejected
        """
        parameterName = aParameterName.strip()
        parameterValue = aParameterValue.strip().split()
        if (len(parameterValue) == 0):
            parameterValue = ""
        else:
            if (len(parameterValue) > 1):
                print "warning: the task handler does not accept multiple\
option values"
            parameterValue = parameterValue[0]
    
        if (parameterName == "useWebDriver" or
            parameterName == "fullScreenMode" or
            parameterName == "aloneOnHost" or
            parameterName == "formatOutput" or
            parameterName == "compressOutput" or
            parameterName == "nativeMathML" or
            parameterName == "runSlowTests" or
            parameterName == "runSkipTests"):
            self.mParameters[parameterName] = (parameterValue == "true")
        elif (parameterName == "port" or
              parameterName == "timeOut"):
            parameterValue = int(parameterValue)
            if (parameterValue == -1):
                if (parameterName == "port"):
                    parameterValue = DEFAULT_SELENIUM_PORT
                else: # timeout
                    parameterValue = DEFAULT_TIMEOUT
            self.mParameters[parameterName] = parameterValue
        elif (parameterName == "host" or
              parameterName == "mathJaxPath" or
              parameterName == "mathJaxTestPath" or
              parameterName == "mathJaxTestPath" or
              parameterName == "operatingSystem" or
              parameterName == "browser" or
              parameterName == "browserMode" or
              parameterName == "browserPath" or
              parameterName == "font" or
              parameterName == "listOfTests" or
              parameterName == "startID"):
            if (parameterValue == "default"):
                if (parameterName == "host"):
                    parameterValue = HOST_LIST[0]
                elif (parameterName == "mathJaxPath"):
                    parameterValue = DEFAULT_MATHJAX_PATH
                else: # mathJaxTestPath
                    parameterValue = DEFAULT_MATHJAX_TEST_PATH
            self.mParameters[parameterName] = parameterValue
        else:
            print "Unknown parameter " + parameterName

    def readParametersFromSocket(self, aRequestHandler):
        """
        @fn readParametersFromSocket(self, aRequestHandler)
        @brief read parameters from the socket and store it in the task

        This function reads lines from the socket until it reaches

        "TASKEDITOR ADD END"

        The function expects to read lines

        "parameterName = parameterValue"

        where the pair (parameterName, parameterValue) is a testing instance
        configuration option. If the option is known, then this parameter is
        added to the task::mParameters table of the task. Otherwise it is
        ignored.
        In any case, the function return True.
        """

        while(True):
            request = aRequestHandler.rfile.readline().strip()
            print request

            if (request == "TASKEDITOR ADD END"):
                break

            item = request.split("=")
            self.setParameter(item[0], item[1])

    def readParametersFromConfigFile(self, aConfigFile):
        """
        @fn readParametersFromConfigFile(self, aConfigFile)
        @brief read parameters from a configuration file
        @param aConfigFile configuration file to use
        """
        configParser = ConfigParser.ConfigParser()
        configParser.optionxform = str # to preserve the case of parameter name
        configParser.readfp(open(aConfigFile))

        for section in ["framework", "platform", "testsuite"]:
            for item in configParser.items(section):
                self.setParameter(item[0], item[1])

    def getScheduledCommand(self):
        """
        @fn getScheduledCommand(self)
        @return the shell command to RESTART the task
        """
        cmd = PYTHON + " "
        cmd += os.getcwdu() + "/taskEditor.py "
        cmd += "RESTART "
        cmd += self.mName
        return cmd
  
class taskHandler:
    """
    @class taskHandler::taskHandler
    @brief A class representing a server handling a task list.
    """

    def __init__(self, aHost, aPort):
        """
        @fn __init__(self, aHost, aPort)

        @param aHost Value to assign to mHost
        @param aPort Value to assign to mPort

        @property mHost
        Host on which the task handler is running.
        
        @property mPort
        Port on which the task handler is running.
        
        @property mTasks
        A hash table of tasks in the task handler, indexed by the task names.
        
        @property mRunningTasksFromHost
        A hash table of tasks which are currently running, indexed by the hosts.

        @property mRunningTaskFromPID
        A hash table of tasks which are currently running, indexed by the PIDs.

        @property mPendingTasksFromHost
        A hash table of task queues, indexed by the hosts. Each task queue is
        the list of tasks which are waiting to run on the host.

        @property mCronTab
        A representation of the crontab used for task scheduling
        """
        self.mHost = aHost
        self.mPort = aPort
        self.mTasks = {}
        self.mRunningTasksFromHost = {}
        self.mRunningTaskFromPID = {}
        self.mPendingTasksFromHost = {}
        self.mCronTab = CronTab()

    def start(self):
        """
        @fn start(self)
        @brief start the server
        """
        print "Task Handler started."
        if (not os.path.exists(TASK_LIST_TXT)):
            # save an empty task list
            self.saveTaskList()
        else:
            self.loadTaskList()
        server = SocketServer.TCPServer((self.mHost, self.mPort),
                                        requestHandler)

        server.serve_forever()

    def stop(self):
        """
        @fn start(self)
        @brief stop the server
        """
        print "Task Handler received SIGINT!"
        self.saveTaskList()

    def getTaskInfo(self, aTaskName):
        """
        @fn getTaskInfo(self, aTaskName)
        @brief Get an HTML representation of properties of a given task.
        @param aTaskName Name of the task from which to retrieve information.
        
        If the task is not in the list, this function returns a message
        indicating so. Otherwise, it calls the task::serializeHTML function.
        """
        if aTaskName not in self.mTasks.keys():
            return "<p>No task '" + aTaskName + "' in the task list.</p>"

        return self.mTasks[aTaskName].serializeHTML();

    def getTaskList(self):
        """
        @fn getTaskList(self)
        @brief return a string representing a task list

        If the task list is empty, one line

        "TASK LIST EMPTY"

        is returned. Otherwise, the returned string starts with the line

        "TASK LIST NONEMPTY"

        and continue with one line per task, each one of the form

        "Task Name	Host Status Progress outputDirectory"
        """
        if (len(self.mTasks) == 0):
            return "TASK LIST EMPTY\n"

        taskList = "TASK LIST NONEMPTY\n"
        for k in self.mTasks.keys():
            taskList += k + " " + self.mTasks[k].serialize() + "\n"
        return taskList

    def loadTaskList(self):
        """
        @fn loadTaskList(self)
        @brief Load the task list from taskList.txt
        """
        fp = file(TASK_LIST_TXT, "r")
        line = fp.readline().strip()
        if (line == "TASK LIST NONEMPTY"):
            while line:
                line = fp.readline().strip()
                items = line.split()
                if (len(items) > 0):
                    if (items[2] == "Running"):
                        status = "Interrupted"
                    elif (items[2] == "Pending"):
                        status = "Inactive"
                    else:
                        status = items[2]
                    t = task(items[0], status, items[4], items[5])
                    t.mProgress = items[3]
                    # host = items[1] is already saved in the config file.
                    t.readParametersFromConfigFile(t.getConfigPath())
                    self.mTasks[t.mName] = t
        fp.close()
    
    def saveTaskList(self):
        """
        @fn saveTaskList(self)
        @brief Save the task list in taskList.txt
        """
        fp = file(TASK_LIST_TXT, "w")
        fp.write(self.getTaskList())
        fp.close()

    def verifyHostStatus(self, aHost):
        """
        @fn verifyHostStatus
        @brief TODO
        """
        for t in gServer.mRunningTasksFromHost[aHost]:
            t.verifyStatus()

    def addTaskToPendingQueue(self, aTask):
        """
        @fn addTaskToPendingQueue(self, aTask)
        @brief add the specified task on the pending queue of aTask.host()
        @param aTask task to add to the pending list
        """
        aTask.mStatus = "Pending"
        h = aTask.host()
        if h in self.mPendingTasksFromHost.keys():
            q = self.mPendingTasksFromHost[h]
            q.append(aTask)
        else:
            q = collections.deque()
            q.append(aTask)
            self.mPendingTasksFromHost[h] = q

    def runNextTasksFromPendingQueue(self, aHost):
        """
        @fn runNextTaskFromPendingQueue(self, aHost)
        @brief run the next pending tasks for the specified host, if possible.
        @param aHost on which we want to run the next task
        """
        if aHost in self.mPendingTasksFromHost.keys():
            q = self.mPendingTasksFromHost[aHost]
            
            while (True):
                if len(q) == 0:
                    del self.mPendingTasksFromHost[aHost]
                    break

                t = q.popleft()

                if (aHost in self.mRunningTasksFromHost.keys()):
                    l = self.mRunningTasksFromHost[aHost]
         
                    if ((len(l) == 1 and l[0].aloneOnHost()) or
                        (t.aloneOnHost())):
                        # A task which should be alone is already running or
                        # The task to push should be alone but l is nonempty:
                        # abort.
                        q.appendleft(t)
                        break

                t.execute()

    def addTaskToRunningList(self, aTask):
        """
        @fn addTaskToRunningList(self, aTask)
        @brief TODO
        """
        h = aTask.host()
        if h not in self.mRunningTasksFromHost.keys():
            self.mRunningTasksFromHost[h] = [aTask]
        else:
            self.mRunningTasksFromHost[h].append(aTask)

    def removeTaskFromRunningList(self, aTask):
        """
        @fn removeTaskFromRunningList(self, aTask)
        @brief TODO
        """
        h = aTask.host()
        l = self.mRunningTasksFromHost[h]
        l.remove(aTask)
        if (len(l) == 0):
            del self.mRunningTasksFromHost[h]

    def addScheduledTask(self, aTask):
        """
        @fn addScheduledTask(self, aTask)
        @brief add the task to the scheduler
        @param aTask task to add
        """
        items = aTask.mSchedule.split(",")
        entry = self.mCronTab.new(aTask.getScheduledCommand(), aTask.mName)
        for i in range(0, 5):
            if (items[i] != "*"):
                entry.slices[i] = int(items[i])

        self.mCronTab.write()

    def removeScheduledTask(self, aTask):
        """
        @fn removeScheduledTask(self, aTask)
        @brief remove the task from the scheduler
        @param aTask task to remove
        """
        self.mCronTab.remove_all(aTask.getScheduledCommand())
        self.mCronTab.write()

gServer = taskHandler(TASK_HANDLER_HOST, TASK_HANDLER_PORT)
 
if __name__ == "__main__":
    if not os.path.exists(TASK_LIST_DIRECTORY):
        os.makedirs(TASK_LIST_DIRECTORY)
    try:
        gServer.start()
    except KeyboardInterrupt:
        gServer.stop()