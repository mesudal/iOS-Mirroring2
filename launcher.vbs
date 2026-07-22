Set objFSO = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
Set objShell = CreateObject("WScript.Shell")
objShell.Environment("Process").Item("PATH") = "C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0"
strPath = strDir & "\ios_mirror_capture.exe"
objShell.CurrentDirectory = strDir
objShell.Run """" & strPath & """", 0, False
