#!/bin/bash
# Create Tauri icons from a source image
# Usage: ./create_tauri_icons.sh <source_image.png>

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <source_image.png>"
    echo "Creates Tauri icons in all required sizes"
    exit 1
fi

SOURCE_IMAGE="$1"
ICONS_DIR="$(dirname "$0")/../src-tauri/icons"

if [ ! -f "$SOURCE_IMAGE" ]; then
    echo "Error: Source image not found: $SOURCE_IMAGE"
    exit 1
fi

# Check if ImageMagick is available
if ! command -v convert &> /dev/null; then
    echo "Error: ImageMagick not found. Install it with:"
    echo "  - macOS: brew install imagemagick"
    echo "  - Linux: apt-get install imagemagick"
    echo "  - Windows: Download from https://imagemagick.org/"
    exit 1
fi

mkdir -p "$ICONS_DIR"

echo "Creating Tauri icons from $SOURCE_IMAGE..."

# Create icons in all required sizes
convert "$SOURCE_IMAGE" -resize 32x32 "$ICONS_DIR/32x32.png"
convert "$SOURCE_IMAGE" -resize 128x128 "$ICONS_DIR/128x128.png"
convert "$SOURCE_IMAGE" -resize 256x256 "$ICONS_DIR/128x128@2x.png"
convert "$SOURCE_IMAGE" -resize 256x256 "$ICONS_DIR/256x256.png"
convert "$SOURCE_IMAGE" -resize 512x512 "$ICONS_DIR/256x256@2x.png"
convert "$SOURCE_IMAGE" -resize 512x512 "$ICONS_DIR/512x512.png"
convert "$SOURCE_IMAGE" -resize 1024x1024 "$ICONS_DIR/512x512@2x.png"

echo "✓ Icons created in $ICONS_DIR"
