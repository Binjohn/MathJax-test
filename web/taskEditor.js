/* -*- Mode: Javascript; tab-width: 2; indent-tabs-mode:nil; -*- */
/* vim: set ts=2 et sw=2 tw=80: */
/* ***** BEGIN LICENSE BLOCK *****
/* Version: Apache License 2.0
 *
 * Copyright (c) 2011 Design Science, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * Contributor(s):
 *   Frederic Wang <fred.wang@free.fr> (original author)
 *
 * ***** END LICENSE BLOCK ***** */

/**
 *  @file taskEditor.js
 *  @brief script for taskEditor.php
 *
 *  This file is used by taskEditor.php
 */

function updateFieldVisibility(aFieldId1, aFieldId2, aValue)
{
    f1 = document.getElementById(aFieldId1);
    f2 = document.getElementById(aFieldId2);
    tag = f1.tagName.toLowerCase();
    if ((tag == "input" &&
         f1.type == "checkbox" && f1.checked == aValue) ||
        (tag == "select" && f1.value == aValue)) {
        f2.style.visibility = "visible";
        f2.style.position = "relative";
    } else {
        f2.style.visibility = "hidden";
        f2.style.position = "absolute";
    }
}

function updateFieldValueFrom(aSelectId, aFieldId)
{
    document.getElementById(aFieldId).value =
        document.getElementById(aSelectId).value
}

function updateSelectIndex(aSelectId1, aSelectId2, aArray)
{
    document.getElementById(aSelectId2).selectedIndex =
        aArray[document.getElementById(aSelectId1).selectedIndex];
}

function openReftestSelector()
{
    window.open("selectReftests.xhtml","","");
}

function updateTaskExists(aTaskName, aExists)
{
    document.getElementById("submit").value = aExists ?
        ("Update parameters of task '" + aTaskName + "'") :
        ("Create a new task '" + aTaskName + "'");
}

function updateField(aParamName, aParamValue)
{
    field = document.getElementById(aParamName);
    tag = field.tagName.toLowerCase();
    
    if (tag == "input") {
        if (field.type == "checkbox") {
            field.checked = (aParamValue == "True");
        } else {
            field.value = aParamValue;
        }
    } else if (tag == "select") {
        field.selectedIndex = 0;
        for (var i = 0; i < field.length; i++) {
            if (field.options[i].value == aParamValue) {
                field.selectedIndex = i;
                break;
            }
        }
    }
}

function updateFieldsFromTaskName()
{
    var request = new XMLHttpRequest();
    var taskName = document.getElementById("taskName").value;
    request.open('GET', 'taskInfo.php?taskName=' + taskName, false);

    request.onreadystatechange = function (aEvent) {
        updateTaskExists(taskName, false);
        if (request.readyState == 4) {
            if (request.status == 200) {
                tree = request.responseXML;
                if (tree) {
                    tables = tree.getElementsByTagName("table");
                    if (tables.length > 0) {
                        updateTaskExists(taskName, true);

                        // First table is special...
                        // Here are possible values to retrieve:
                        // - Result directory
                        // - Scheduled date
                        // XXXfred, for now they are just ignored.

                        // Update the field from the information of the tables
                        for (var i = 1; i < tables.length; i++) {
                            trs = tables[i].getElementsByTagName("tr");
                            for (var j = 0; j < trs.length; j++) {
                                tr = trs[j];
                                paramName = tr.
                                    getElementsByTagName("th")[0].innerHTML;
                                paramValue = tr.
                                    getElementsByTagName("td")[0].innerHTML;
                                updateField(paramName, paramValue);
                            }
                        }
                    }
                }
            }
            updateAllFields();
        }
    }

    request.send(null);
}

function updateAllFields()
{
    updateFieldVisibility("taskSchedule", "crontabParameters", true);
    updateFieldVisibility("useWebDriver", "fullScreenMode_", false);
    updateFieldVisibility("useWebDriver", "aloneOnHost_", true);
    updateFieldValueFrom("host_select", "host");
    updateFieldValueFrom("taskName", "outputDirectory");
    updateFieldVisibility("browser", "browserMode_", "MSIE")
    updateSelectIndex("host_select", "operatingSystem", HOST_LIST_OS);
}

function init()
{
    updateAllFields();
    updateFieldsFromTaskName();
}