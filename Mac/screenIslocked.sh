#!/bin/sh

function screenIsLocked { [ "$(/usr/libexec/PlistBuddy -c "print :IOConsoleUsers:0:CGSSessionScreenIsLocked" /dev/stdin 2>/dev/null <<< "$(ioreg -n Root -d1 -a)")" = "true" ] && return 0 || return 1; }
function screenIsUnlocked { [ "$(/usr/libexec/PlistBuddy -c "print :IOConsoleUsers:0:CGSSessionScreenIsLocked" /dev/stdin 2>/dev/null <<< "$(ioreg -n Root -d1 -a)")" != "true" ] && return 0 || return 1; }

if screenIsLocked; then
    echo "Screen locked"
fi

if screenIsUnlocked; then
    echo "Screen unlocked"
fi

if ! screenIsLocked; then
    echo "Screen unlocked (inverse logic)"
fi

if ! screenIsUnlocked; then
    echo "Screen locked (inverse logic)"
fi

# function screenIsUnlocked { [ "$(/usr/libexec/PlistBuddy -c "print :IOConsoleUsers:0:CGSSessionScreenIsLocked" /dev/stdin 2>/dev/null <<< "$(ioreg -n Root -d1 -a)")" != "true" ] && echo "0" || open -a 解锁Mac.app; } && screenIsUnlocked