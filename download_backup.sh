#!/bin/bash
# Script to download the latest backup from remote server to WSL
# Usage: ./download_backup.sh

REMOTE_HOST="root@203.60.1.63"
REMOTE_PATH="/root"
LOCAL_DOWNLOAD_DIR="$HOME/backups"
BACKUP_PATTERN="allnewsandbox.tar.gz"

# Create local download directory if it doesn't exist
mkdir -p "$LOCAL_DOWNLOAD_DIR"

echo "🔍 Checking for latest backup on $REMOTE_HOST..."

# Find the latest backup file on remote server
LATEST_BACKUP=$(ssh "$REMOTE_HOST" "ls -t $REMOTE_PATH/$BACKUP_PATTERN 2>/dev/null | head -1")

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No backup file found matching pattern: $BACKUP_PATTERN"
    echo "📋 Available files on remote server:"
    ssh "$REMOTE_HOST" "ls -lh $REMOTE_PATH/*.tar.gz 2>/dev/null || echo 'No .tar.gz files found'"
    exit 1
fi

# Extract filename from full path
BACKUP_FILENAME=$(basename "$LATEST_BACKUP")
LOCAL_FILE="$LOCAL_DOWNLOAD_DIR/$BACKUP_FILENAME"

echo "📦 Found backup: $LATEST_BACKUP"
echo "📊 Getting file size..."
REMOTE_SIZE=$(ssh "$REMOTE_HOST" "stat -c%s '$LATEST_BACKUP' 2>/dev/null || echo '0'")
if [ "$REMOTE_SIZE" != "0" ]; then
    SIZE_MB=$((REMOTE_SIZE / 1024 / 1024))
    echo "   Size: ${SIZE_MB} MB"
fi

echo ""
echo "⬇️  Downloading to: $LOCAL_FILE"
echo "   This may take a while depending on file size..."
echo ""

# Download the file using scp with progress
scp "$REMOTE_HOST:$LATEST_BACKUP" "$LOCAL_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Download complete!"
    echo "📁 File saved to: $LOCAL_FILE"
    if [ -f "$LOCAL_FILE" ]; then
        LOCAL_SIZE=$(stat -c%s "$LOCAL_FILE" 2>/dev/null || stat -f%z "$LOCAL_FILE" 2>/dev/null)
        LOCAL_SIZE_MB=$((LOCAL_SIZE / 1024 / 1024))
        echo "📊 Local file size: ${LOCAL_SIZE_MB} MB"
        
        # Verify file integrity
        if [ "$REMOTE_SIZE" != "0" ] && [ "$REMOTE_SIZE" = "$LOCAL_SIZE" ]; then
            echo "✅ File size matches - download verified"
        fi
    fi
else
    echo ""
    echo "❌ Download failed!"
    exit 1
fi
