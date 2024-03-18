#!/bin/bash

# 设定目标目录，如果脚本调用时没有提供，则使用当前目录
TARGET_DIR="${1:-.}"

# 删除所有.pyc文件和__pycache__目录
find "$TARGET_DIR" -type f -name "*.pyc" -exec rm -f {} +
find "$TARGET_DIR" -type d -name "__pycache__" -exec rm -rf {} +

echo "Cleanup completed."

