#通过AppleScript连接蓝牙音响，需要把蓝牙图标放置在菜单栏，在“自动操作”app内保存为应用程序后设置为开机启动

#BigSur
set DeviceName to "方糖(D0:44)"
tell application "System Events"
	tell application process "ControlCenter"
		set btMenu to menu bar item "蓝牙" of menu bar 1
		tell btMenu to click
		# entire contents
		set btCheckbox to checkbox 1 of scroll area 1 of group 1 of window "控制中心" whose title contains DeviceName
		if exists btCheckbox then
			if value of btCheckbox is 1 then
				set btCheckboxValue to 0
				tell btCheckbox to click
				tell btMenu to click
				return "断开连接中..."
			else
				set btCheckboxValue to 1
				tell btCheckbox to click
				tell btMenu to click
				return "连接中..."
			end if
		else
			click btMenu
			return "没找到设备"
		end if
	end tell
end tell

#Monterey 系统UI变更，找不到checkbox 1 of scroll area 1 of group 1 of window "控制中心" whose title contains DeviceName
#通过直接点击坐标变通实现
tell application "System Events"
	tell application process "ControlCenter"
		set btMenu to menu bar item "蓝牙" of menu bar 1
		tell btMenu to click
	end tell
	delay 0.5
	click at {1510, 110}
	delay 0.3
	key code 53
end tell