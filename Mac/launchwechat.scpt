-- 配置相对点击坐标（窗口左上角为原点）
set relativeX to 135
set relativeY to 290
set cliclickPath to "/opt/homebrew/bin/cliclick"

-- 记录当前鼠标位置
set oldMousePos to do shell script quoted form of cliclickPath & " p"
set {oldX, oldY} to my parseCoords(oldMousePos)

-- 检查微信是否运行
tell application "System Events"
	set wxRunning to (processes whose name is "WeChat") ≠ {}
end tell

if wxRunning then return -- 已运行则退出

-- 启动微信
tell application "WeChat" to activate

-- 等待窗口出现（最多 6 秒，每 0.5s 检查一次）
tell application "System Events"
	repeat 12 times
		if exists window 1 of process "WeChat" then exit repeat
		delay 0.5
	end repeat
end tell

-- 获取窗口位置
tell application "System Events"
	tell process "WeChat"
		set {wxPosX, wxPosY} to position of window 1
	end tell
end tell

-- 计算屏幕坐标（左上角 + 相对位置）
set clickX to wxPosX + relativeX
set clickY to wxPosY + relativeY

-- 执行点击（临时把鼠标移动过去点击）
do shell script quoted form of cliclickPath & " m:" & clickX & "," & clickY
do shell script quoted form of cliclickPath & " c:."

-- 恢复鼠标到原位置
do shell script quoted form of cliclickPath & " m:" & oldX & "," & oldY

-- 隐藏微信窗口（Cmd + H）
delay 0.5
tell application "System Events"
	keystroke "h" using {command down}
end tell


-- ----------- 工具函数：解析坐标 -----------
on parseCoords(t)
	set AppleScript's text item delimiters to {","}
	set x to item 1 of text items of t
	set y to item 2 of text items of t
	return {x as integer, y as integer}
end parseCoords
