set ws=wscript.createobject("wscript.shell")
ws.run "CheckNetIsolation.exe loopbackexempt -d -p=S-1-15-2-2023288336-3861689935-4012331332-3972394312-2039088593-711845402-982279670",0
ws.run "explorer.exe shell:appsFolder\903DB504.QQ_a99ra4d2cbcxa!App",0
WScript.Sleep 5000
ws.run "CheckNetIsolation.exe loopbackexempt -a -p=S-1-15-2-2023288336-3861689935-4012331332-3972394312-2039088593-711845402-982279670",0