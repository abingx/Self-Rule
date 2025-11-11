tell application "System Events"
	key code 123
	delay 0.1
	set pass to "{mac pw}"
	repeat with i from 1 to count characters of pass
		keystroke (character i of pass)
	end repeat
	keystroke return
end tell


#快捷指令 判断是否在锁屏状态
function screenIsUnlocked { [ "$(/usr/libexec/PlistBuddy -c "print :IOConsoleUsers:0:CGSSessionScreenIsLocked" /dev/stdin 2>/dev/null <<< "$(ioreg -n Root -d1 -a)")" != "true" ] && echo "0" || open -a 解锁Mac.app; } && screenIsUnlocked