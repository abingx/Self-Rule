set ws=WScript.CreateObject("WScript.Shell")
If WScript.Arguments.Length = 0 Then 
  Set ObjShell = CreateObject("Shell.Application") 
  ObjShell.ShellExecute "wscript.exe" _ 
  , """" & WScript.ScriptFullName & """ RunAsAdministrator", , "runas", 1 
  WScript.Quit 
End if 
ws.Run "sing-box run -c ""C:\Users\bing\sing-box\fish_Windows.json""",0