-- 配置相对点击坐标（窗口左上角为原点）
set relativeX to 135
set relativeY to 290
set cliclickPath to "/opt/homebrew/bin/cliclick"

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

-- 使用 cliclick 虚拟点击（不移动鼠标）
do shell script quoted form of cliclickPath & " c:" & clickX & "," & clickY
