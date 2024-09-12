#!/bin/bash
#重新部署
cd /Library/Input\ Methods/Squirrel.app/Contents/MacOS && ./Squirrel --reload
#同步词库
cd /Library/Input\ Methods/Squirrel.app/Contents/MacOS && ./Squirrel --sync
