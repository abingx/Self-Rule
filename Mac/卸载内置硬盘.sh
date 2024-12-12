#!/bin/zsh
# 延迟 30 秒
echo "将等待 30 秒后执行后续操作..."
sleep 30
# 获取 "Macintosh HD" 的磁盘标识符
mac_disk_id=$(diskutil list | grep "Macintosh HD" | awk '{print $NF}' | head -n 1)
# 获取 "Data" 的磁盘标识符
data_disk_id=$(diskutil list | grep "Data" | awk '{print $NF}' | head -n 1)
# 检查 "Macintosh HD" 磁盘是否存在
if [[ -z "$mac_disk_id" ]]; then
    echo "未找到磁盘 'Macintosh HD'，请检查磁盘名称"
else
    # 检查 "Macintosh HD" 是否已挂载，处理不确定数量的空格
    if diskutil info "$mac_disk_id" | grep -qE "^\s*Mounted:\s*Yes"; then
        echo "$mac_disk_id 已挂载，正在卸载..."
        diskutil unmount "$mac_disk_id"
    else
        echo "$mac_disk_id 已经被卸载，跳过卸载操作"
    fi
fi
# 检查 "Data" 磁盘是否存在
if [[ -z "$data_disk_id" ]]; then
    echo "未找到磁盘 'Data'，请检查磁盘名称"
else
    # 检查 "Data" 是否已挂载，处理不确定数量的空格
    if diskutil info "$data_disk_id" | grep -qE "^\s*Mounted:\s*Yes"; then
        echo "$data_disk_id 已挂载，正在卸载..."
        diskutil unmount "$data_disk_id"
    else
        echo "$data_disk_id 已经被卸载，跳过卸载操作"
    fi
fi