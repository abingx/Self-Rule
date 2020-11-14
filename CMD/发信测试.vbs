Dim WshShell
Set WshShell = WScript.CreateObject("WScript.Shell")
WshShell.run"cmd"
WshShell.AppActivate"c:\windows\system32\cmd.exe"
WScript.Sleep 200
WshShell.SendKeys"telnet smtp.qq.com 25"
WshShell.SendKeys"{ENTER}"
WScript.Sleep 200
WshShell.SendKeys"helo goodmorning"
WshShell.SendKeys"{ENTER}"
WScript.Sleep 200
WshShell.SendKeys"auth login"
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"MjI5Mjk1MDVAcXEuY29t"
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"YnJheWhucm5uaGFmYmlpYw=="
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"mail from:<22929505@qq.com>"
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"rcpt to:<allin_mbx@mail.sdufe.edu.cn>"
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"data"
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"from:Mail test"
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"to:EDU"
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"subject:Mail test"
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"{ENTER}"
WshShell.SendKeys"This is a test for EDU mail receive."
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"."
WScript.Sleep 2000
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"quit"
WshShell.SendKeys"{ENTER}"
WScript.Sleep 2000
WshShell.SendKeys"exit"
WshShell.SendKeys"{ENTER}"

