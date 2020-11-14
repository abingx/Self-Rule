echo off
set lj=%cd%
xcopy %USERPROFILE%\.config\clash %lj%\ /e
rd /s/q %USERPROFILE%\.config\clash
mklink/j "%USERPROFILE%\.config\clash" "%lj%\"