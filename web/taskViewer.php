<?php
/* ***** BEGIN LICENSE BLOCK *****
/* Version: Apache License 2.0
 *
 * Copyright (c) 2011-2015 MathJax Consortium, Inc.
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
 *  @file taskViewer.php
 *  @brief Gives a preview of all the tasks in the task lists.
 *
 *  This PHP script tries to connect to a task handler. It displays an error
 *  message if it fails. Otherwise, it gets the answer of the server:
 *  - If it is "TASK LIST EMPTY" it displays a message providing that information.
 *  - If it is "TASK LIST NONEMPTY", it displays a HTML table. It reads the
 *    socket line by line until the end and convert each line into a row giving
 *    information on a task. The table contains also various useful links to
 *    task information, test outputs and command of @ref commandHandler.php.
 */

  echo '<?xml version="1.0" encoding="UTF-8"?>';
  include('config.php');

  /**
   *  @brief print HTML code to generate a command button.
   *  @param aTaskName name of the task to control
   *  @param aCommand name of the command to execute
   *  @param aNewName whether the user should pass a new task name (used by
   *         clone and rename commands).
   */
  function commandButton($aTaskName, $aCommand, $aNewName = False)
  {
  $c = strtolower($aCommand);

  if ($aNewName) { echo ' ['; }
  echo '<form action="commandHandler.php" method="post">';
  echo '<input name="command" type="text" readonly="readonly"';
  echo       ' value="'.$aCommand.'" class="hiddenField"/>';
  echo '<input name="taskName" type="text" readonly="readonly"';
  echo       ' value="'.$aTaskName.'" class="hiddenField"/>';
  if ($aNewName) {
    echo '<input name="newName" type="text" value="" size="8" ';
    echo         'required="required" ';
    echo         'pattern="([a-z]|[A-Z]|[0-9]|\-){1,40}"/>';
  }
  echo '<input type="submit" value="" class="submitField"';
  echo       ' style="background-image: url(icons/'.$c.'.png)" ';
  echo       ' title="'.$c.' task" />';
  echo '</form>';
  if ($aNewName) { echo '] '; }
  }

  /**
   *
   *
   */
  function outputLogo($File, $type)
  {
  if (file_exists($File)) {
    echo ' <a href="'.$File.'"><img ';
    echo 'src="icons/'.$type.'-output.png" ';
    echo 'alt="'.$type.'output" title="'.$type.' output"/></a>';
  }
  }
?>

<!DOCTYPE html>
<html>
  <head>
    <title>Task Viewer</title>
    <!-- Copyright (c) 2011-2015 MathJax Consortium, Inc.
         License: Apache License 2.0 -->
    <meta http-equiv="content-type" content="text/html; charset=UTF-8" />
    <link rel="stylesheet" type="text/css" href="default.css"/>
    <link type="text/css" rel="stylesheet" href="taskViewer.css"/>
    <script type="text/javascript" src="taskViewer.js"></script>
  </head>

  <body>
    <div class="related">
      <h3>Navigation</h3>
      <ul>
      <ul>
        <li><a href="./">Back to home</a></li> 
      </ul>
      </ul>
    </div>  

    <div class="body">
      <h1>Task Viewer</h1>

      <?php
        $file = fsockopen($TASK_HANDLER_HOST, $TASK_HANDLER_PORT);
        if ($file) {
          fwrite($file, "TASKVIEWER\n");
          $line = trim(fgets($file));
          if ($line == "TASK LIST EMPTY") {
            echo "<p>The task list is empty.</p>";
            fclose($file);
          } else {
            // Get the task list
            $taskList = array();
            $taskNames = array();
            $taskHosts = array();
            $taskPriorities = array();
            $i = 0;
            while(!feof($file)) {
              $line = trim(fgets($file));
	      $row = explode(" ", $line, 8);
              if (count($row) == 8) {
                $taskList[$i] = $row;
                $taskNames[$i] = $row[0];
                $taskHosts[$i] = $row[1];
                $taskPriorities[$i] = $row[2];
	        $i++;
	      }
            }
            fclose($file);

            // Sort the task list by (Host, Priority, Name)
            array_multisort($taskHosts, SORT_ASC,
	                    $taskPriorities, SORT_ASC,
			    $taskNames, SORT_ASC,
			    $taskList);

            echo '<table id="taskList">';
            echo '<tr>';
            echo '<th>Host</th>';
            echo '<th>Priority</th>';
            echo '<th>Task Name</th>';
            echo '<th>Status</th>';
            echo '<th>Progress</th>';
            echo '<th>Results</th>';
            echo '<th>Actions</th>';
            echo '</tr>';

            foreach ($taskList as $taskProperties) {
                $taskName = $taskProperties[0];
                $host = $taskProperties[1];
                $priority = $taskProperties[2];
                $status = $taskProperties[3];
                $progress = $taskProperties[4];
                $resultDir = $taskProperties[5];
                $resultFileName = $taskProperties[6];
                $schedule = $taskProperties[7];

                echo '<tr>';
                echo '<td><a href="hostInfo.php?host='.$host.'">';
                echo $host.'</a></td>';
                echo '<td>'.$priority.'</td>';
                echo '<td><a href="taskInfo.php?taskName='.$taskName.'">';
                echo $taskName.'</a></td>';
                echo '<td>';
                if ($status == "Killed") {
                  echo '<a href="taskInfo.php?taskName='.$taskName;
                  echo '#exceptionError">'.$status.'</a>';
		            } else {
                  echo $status;
		            }

                $isScheduled = ($schedule != "None");
                if ($isScheduled) {
                  echo " (scheduled)";
                }
                echo '</td>';
  
                echo '<td>'.$progress.'</td>';
                echo '<td>';
                $resultDir2 = "results/".$resultDir;
                if (file_exists($resultDir2)) {
                  echo '<a href="'.$resultDir2.'">'.$resultDir.'</a> ';
                  $textOutput = $resultDir2.$resultFileName.".txt";
                  $formattedOutput = $resultDir2.$resultFileName.".html";

                  if (file_exists($textOutput)) {
                    commandButton($taskName, "FORMAT");
                  }

                  if ($status != "Running") {
                    // We choose the compressed versions if they exist
                    if (file_exists($textOutput.".gz")) {
                      $textOutput = $textOutput.".gz";
                    }
                    if (file_exists($formattedOutput.".gz")) {
                      $formattedOutput = $formattedOutput.".gz";
                    }
                  }

                  outputLogo($textOutput, "text");
                  outputLogo($formattedOutput, "formatted");
                } else {
                  echo $resultDir;
                }
                echo '</td>';

                echo '<td>';

                echo '<input class="taskCheckbox" type="checkbox"';
                echo '       name="checkbox-'.$taskName.'"/>'; 

                if ($status != "Running") {
                  echo '<a class="noIcon"';
                  echo '   href="taskEditor.php?taskName='.$taskName.'">';
                  echo ' <img src="icons/edit.png" width="16" height="16"';
                  echo 'alt="edit task" title="edit task"/></a>';
                }

                if ($status == "Pending") {
                 commandButton($taskName, "RUN");
                 commandButton($taskName, "REMOVE");
                } else if ($status == "Running") {
                  commandButton($taskName, "STOP");
                } else if($status == "Interrupted" || $status == "Killed") {
                  if (!$isScheduled) {
                    commandButton($taskName, "RUN");
                    commandButton($taskName, "RESTART");
                  }
                  commandButton($taskName, "REMOVE");
                } else if ($status == "Complete") {
                  if (!$isScheduled) {
                    commandButton($taskName, "RESTART");
                  }
                  commandButton($taskName, "REMOVE");
                } else if ($status == "Inactive") {
                  if (!$isScheduled) {
                    commandButton($taskName, "RUN");
                  }
                  commandButton($taskName, "REMOVE");
                }

              commandButton($taskName, "CLONE", True);
              commandButton($taskName, "RENAME", True);
              echo '</td>';
              echo '</tr>';
            }
            echo '</table>';

            echo '<p>';
            echo '<form name="multipleTasks" action="commandHandler.php"';
            echo '      method="post">';
            echo '<a class="multipleTaskCommand"
                     href="javascript:runMultipleTasks();">
                     Run selected tasks <img src="icons/run.png"/></a> ';
            echo '<a class="multipleTaskCommand"
                     href="javascript:restartMultipleTasks();">
                 Restart selected tasks <img src="icons/restart.png"/></a> ';
            echo '<a class="multipleTaskCommand"
                     href="javascript:stopMultipleTasks();">
                  Stop selected tasks <img src="icons/stop.png"/></a> ';
            echo '<a class="multipleTaskCommand"
                     href="javascript:removeMultipleTasks();">
                 Remove selected tasks <img src="icons/remove.png"/></a> ';
            echo '<input name="command" id="multipleTasksCommand"';
            echo '       type="text" class="hiddenField" readonly="readonly"/>';
            echo '<input name="taskList" id="multipleTasksList"';
            echo '       type="text" readonly="readonly"';
            echo       ' value="" class="hiddenField"/>';
            echo '</form>';
            echo '<a class="multipleTaskCommand"
                     href="javascript:taskCheckboxes(true);">
                     Check all tasks</a> ';
            echo '<a class="multipleTaskCommand"
                     href="javascript:taskCheckboxes(false);">
                     Uncheck all tasks</a>';
            echo '</p>';
          }
        } else {
          echo '<p>'.$ERROR_CONNECTION_TASK_HANDLER.'</p>';
        }
      ?>

       <ul>
         <li><a class="noIcon" href="taskEditor.php">Task Editor</a></li>
         <?php
            echo '<li><a href="http://'.$SELENIUM_SERVER_HUB_HOST.':'.$SELENIUM_SERVER_HUB_PORT.'/grid/console">Grid Hub Console</a></li>';
         ?>
       </ul>
    </div>
  </body>
</html>
