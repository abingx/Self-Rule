@echo off
cd %USERPROFILE%\plum
call rime-install iDvel/rime-ice:others/recipes/full
echo rime-ice全量更新完毕

xcopy /Y /E D:\OneDrive\应用\rimesync\rime个人配置 %APPDATA%\Rime
echo 个人配置复制完毕
