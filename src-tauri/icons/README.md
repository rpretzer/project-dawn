# Tauri Icons

This directory should contain application icons in multiple sizes for Tauri.

## Required Sizes

- `32x32.png` - Small icon
- `128x128.png` - Medium icon
- `128x128@2x.png` (256x256) - Medium @2x
- `256x256.png` - Large icon
- `256x256@2x.png` (512x512) - Large @2x
- `512x512.png` - Extra large icon
- `512x512@2x.png` (1024x1024) - Extra large @2x

## Generation

Use the provided script to generate icons from a source image:

```bash
./scripts/create_tauri_icons.sh icon.png
```

Or manually create icons using ImageMagick:

```bash
convert icon.png -resize 32x32 icons/32x32.png
convert icon.png -resize 128x128 icons/128x128.png
# ... etc
```

## Placeholder

Until icons are generated, Tauri will use default icons. The application will build and run, but without custom branding.

## Source Image

Create or obtain a 1024x1024 PNG image as the source. Recommended:
- Square aspect ratio
- Transparent background (PNG with alpha)
- High resolution (1024x1024 minimum)
- Simple, recognizable design
