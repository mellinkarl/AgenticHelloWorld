#!/bin/bash

# 设置变量
PACKAGE_NAME="amie"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="${PACKAGE_NAME}_${TIMESTAMP}.tar.gz"

echo "🧹 开始清理打包 AMIE 项目..."
echo "📦 包名: $ARCHIVE_NAME"

# 清理 Python 缓存文件
echo "🧽 清理 Python 缓存文件..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

# 清理系统文件
echo "🗑️  清理系统文件..."
find . -name ".DS_Store" -delete 2>/dev/null || true
find . -name "Thumbs.db" -delete 2>/dev/null || true

# 创建临时打包目录
TEMP_DIR=$(mktemp -d)
echo "📁 创建临时目录: $TEMP_DIR"

# 复制文件到临时目录，排除不需要的文件
echo "📋 复制文件到临时目录..."
rsync -av --progress ./ $TEMP_DIR/ \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.DS_Store' \
    --exclude='.env*' \
    --exclude='*.log' \
    --exclude='.git/' \
    --exclude='.packignore' \
    --exclude='package.sh' \
    --exclude='*.tmp' \
    --exclude='*.temp'

# 进入临时目录并创建压缩包
cd $TEMP_DIR
echo "🗜️  创建压缩包..."
tar -czf "$ARCHIVE_NAME" .

# 移动压缩包到原目录
mv "$ARCHIVE_NAME" "/Users/harryzhang/git/AgenticHelloWorld/backend/amie/"

# 清理临时目录
cd /Users/harryzhang/git/AgenticHelloWorld/backend/amie/
rm -rf $TEMP_DIR

echo "✅ 打包完成！"
echo "📦 文件位置: $(pwd)/$ARCHIVE_NAME"
echo "📊 文件大小: $(du -h "$ARCHIVE_NAME" | cut -f1)"

# 显示压缩包内容概览
echo "📋 压缩包内容概览:"
tar -tzf "$ARCHIVE_NAME" | head -20
echo "..."
