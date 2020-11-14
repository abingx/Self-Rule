@echo off
set lj=%cd%
rd /s/q %USERPROFILE%\.config\clash
xcopy %lj% %USERPROFILE%\.config\clash\ /e
del %USERPROFILE%\.config\clash\*.bat
cd..
rd /s/q %lj%\