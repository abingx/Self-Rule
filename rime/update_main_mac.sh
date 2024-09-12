#!/bin/bash
# 重置rime.json记录设备更新记录文件
cp /Volumes/Data/OneDrive/应用/rimesync/rime个人配置/rime.json ~/Library/Mobile\ Documents/iCloud~is~workflow~my~workflows/Documents/rime.json
echo "rime.json已重置"
# 拉取雾凇仓库
cd /Volumes/Data/OneDrive/应用/rimesync/rime-ice || exit
git pull
echo "雾凇拼音拉取完毕"
# 复制词典文件
cp /Volumes/Data/OneDrive/应用/rimesync/rime-ice/rime_ice.dict.yaml /Volumes/Data/OneDrive/应用/rimesync/rime个人配置/rime-ice/my.dict.yaml
# 进入个人配置目录
cd /Volumes/Data/OneDrive/应用/rimesync/rime个人配置/rime-ice || exit
# 获取所有词典文件名
fileNames=()
for file in mydicts/*.dict.yaml; do
  dir=$(basename "$(dirname "$file")")
  name=$(basename "$file" .dict.yaml)
  fileNames+=("$dir/$name")
done
filesString=$(IFS=,; printf "%s" "${fileNames[*]}")
# 更新 my.dict.yaml 文件
awk -v files="$filesString" '
/# - cn_dicts\/mydict/ {
  print;
  split(files, fileList, ",");
  for (i in fileList) {
    print "  - " fileList[i];
  }
  next;
}
{
  print;
}' my.dict.yaml > temp.yaml && mv temp.yaml my.dict.yaml
echo "my.dict.yaml更新完毕"
# 复制 鼠须管 配置文件到目标位置
cp -R /Volumes/Data/OneDrive/应用/rimesync/rime-ice/* ~/Library/Rime
cp -R /Volumes/Data/OneDrive/应用/rimesync/rime个人配置/rime-ice/* ~/Library/Rime 
cp -R /Volumes/Data/OneDrive/应用/rimesync/rime个人配置/squirrel/* ~/Library/Rime 
# 复制 Hamster 配置文件到目标位置
cp -R /Volumes/Data/OneDrive/应用/rimesync/rime-ice/* ~/Library/Mobile\ Documents/iCloud~dev~fuxiao~app~hamsterapp/Documents/RIME/Rime
cp -R /Volumes/Data/OneDrive/应用/rimesync/rime个人配置/rime-ice/* ~/Library/Mobile\ Documents/iCloud~dev~fuxiao~app~hamsterapp/Documents/RIME/Rime
cp -R /Volumes/Data/OneDrive/应用/rimesync/rime个人配置/hamster/* ~/Library/Mobile\ Documents/iCloud~dev~fuxiao~app~hamsterapp/Documents/RIME/Rime
echo "更新完毕"
