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

-- 等待窗口出现并准备好被查询
tell application "System Events"
	-- 等待窗口出现
	repeat 20 times
		if exists (window 1 of process "WeChat") then
			-- 窗口出现后，再短暂等待一下，确保其尺寸和位置信息已稳定
			delay 0.2
			exit repeat
		end if
		delay 0.3
	end repeat
end tell

-- 记录窗口初始位置与尺寸
tell application "System Events"
	tell process "WeChat"
		set {wxPosX, wxPosY} to position of window 1
		set {wxWidthBefore, wxHeightBefore} to size of window 1
	end tell
end tell

-- 计算点击坐标（左上角 + 相对位置）
set clickX to wxPosX + relativeX
set clickY to wxPosY + relativeY

-- 执行点击（临时把鼠标移动过去点击）
do shell script quoted form of cliclickPath & " m:" & clickX & "," & clickY
do shell script quoted form of cliclickPath & " c:."

-- 恢复鼠标到原位置
do shell script quoted form of cliclickPath & " m:" & oldX & "," & oldY

-- 监控窗口尺寸变化（判断是否成功登录）
tell application "System Events"
	repeat 20 times -- 最长 10 秒
		try
			tell process "WeChat"
				set {wxWidthNow, wxHeightNow} to size of window 1
			end tell
			
			if wxWidthNow > wxWidthBefore or wxHeightNow > wxHeightBefore then
				exit repeat
			end if
		end try
		delay 0.5
	end repeat
end tell

-- 隐藏微信窗口 (使用更可靠的 GUI 脚本)
tell application "System Events"
    -- 明确告诉微信进程执行按键操作
    tell process "WeChat"
        keystroke "h" using {command down}
    end tell
end tell


-- ----------- 工具函数：解析坐标（安全版） -----------
on parseCoords(t)
	set oldDelims to AppleScript's text item delimiters
	set AppleScript's text item delimiters to {","}
	set x to item 1 of text items of t
	set y to item 2 of text items of t
	set AppleScript's text item delimiters to oldDelims
	return {x as integer, y as integer}
end parseCoords