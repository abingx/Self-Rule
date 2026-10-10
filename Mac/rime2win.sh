#!/bin/bash
mkdir ~/rime2win

# 复制非隐藏文件及子目录
cp -a ~/GitHub/rime-ice/* ~/rime2win/
cp -a ~/GitHub/rime-conf-sync/conf/rime-ice/* ~/rime2win/
cp -a ~/GitHub/rime-conf-sync/conf/weasel/* ~/rime2win/
cp -a ~/GitHub/rime-conf-sync/sync ~/rime2win/

# 打包到 ~/Downloads
tar -czf ~/Downloads/rime2win.tar.gz -C ~ rime2win

# 删除原目录
rm -rf ~/rime2win
