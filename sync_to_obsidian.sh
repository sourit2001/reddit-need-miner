#!/bin/bash
# sync_to_obsidian.sh
# 功能：从 GitHub 拉取最新分析结果，只将汇总报告同步到本地 Obsidian iCloud 目录
# 个人帖子详情只推飞书，不进 Obsidian
# 用法：手动运行，或通过 crontab 定时自动运行

REPO_DIR="/Users/lizhu/Downloads/CCR/SSH/reddit-need-miner"
OBSIDIAN_DIR="/Users/lizhu/Library/Mobile Documents/iCloud~md~obsidian/Documents/my ai work/obsidian_sync"
LOG_FILE="$REPO_DIR/sync.log"

echo "[$( date '+%Y-%m-%d %H:%M:%S' )] 开始同步汇总报告..." | tee -a "$LOG_FILE"

# 1. 进入仓库目录，拉取最新内容
cd "$REPO_DIR"
git fetch origin main
git reset --hard origin/main 2>&1 | tee -a "$LOG_FILE"

# 2. 确保 Obsidian 目标目录存在
mkdir -p "$OBSIDIAN_DIR"

# 3. 只同步 汇总报告-*.md，个人帖子不进 Obsidian
COPIED=0
for file in "$REPO_DIR/obsidian_sync/"汇总报告-*.md; do
    [ -f "$file" ] || continue
    filename=$(basename "$file")
    dest="$OBSIDIAN_DIR/$filename"
    # 只复制不存在或内容有变化的文件
    if [ ! -f "$dest" ] || ! cmp -s "$file" "$dest"; then
        cp "$file" "$dest"
        echo "  ✅ 已同步: $filename" | tee -a "$LOG_FILE"
        COPIED=$((COPIED + 1))
    fi
done

if [ "$COPIED" -eq 0 ]; then
    echo "  ℹ️  没有新的汇总报告需要同步" | tee -a "$LOG_FILE"
else
    echo "  🎉 共同步了 $COPIED 份汇总报告" | tee -a "$LOG_FILE"
fi

echo "[$( date '+%Y-%m-%d %H:%M:%S' )] 同步完成" | tee -a "$LOG_FILE"
