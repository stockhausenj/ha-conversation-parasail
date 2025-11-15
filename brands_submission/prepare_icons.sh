#!/bin/bash
# Script to help prepare Parasail Conversation icons for Home Assistant brands repository

set -e

OUTPUT_DIR="custom_integrations/parasail_conversation"

echo "Parasail Conversation - Icon Preparation Script"
echo "================================================"
echo ""

# Check if ImageMagick is installed
if ! command -v convert &> /dev/null; then
    echo "⚠️  ImageMagick is not installed."
    echo "   Install it to automatically convert SVG to PNG:"
    echo "   - macOS: brew install imagemagick"
    echo "   - Ubuntu/Debian: sudo apt-get install imagemagick"
    echo "   - Arch: sudo pacman -S imagemagick"
    echo ""
fi

# Check if Inkscape is installed
if ! command -v inkscape &> /dev/null; then
    echo "ℹ️  Inkscape is not installed (alternative to ImageMagick)."
    echo "   - macOS: brew install inkscape"
    echo "   - Ubuntu/Debian: sudo apt-get install inkscape"
    echo ""
fi

# Try to download Parasail logo
echo "Attempting to download Parasail logo from website..."
LOGO_URL="https://cdn.prod.website-files.com/68dc9f24a893fa7f1dfbf2ee/68dca057dfebb8b6760f24a8_logo.svg"

if command -v curl &> /dev/null; then
    curl -f "$LOGO_URL" -o parasail_logo.svg 2>/dev/null && echo "✓ Downloaded parasail_logo.svg" || echo "⚠️  Could not download logo automatically"
elif command -v wget &> /dev/null; then
    wget -q "$LOGO_URL" -O parasail_logo.svg && echo "✓ Downloaded parasail_logo.svg" || echo "⚠️  Could not download logo automatically"
else
    echo "⚠️  Neither curl nor wget found. Please download the logo manually."
fi

echo ""

# If logo exists, try to convert
if [ -f "parasail_logo.svg" ]; then
    echo "Found parasail_logo.svg, attempting conversion..."

    if command -v convert &> /dev/null; then
        echo "Using ImageMagick to create PNG files..."

        # Create icons (square)
        convert parasail_logo.svg -background none -resize 256x256 -gravity center -extent 256x256 "$OUTPUT_DIR/icon.png"
        echo "✓ Created icon.png (256x256)"

        convert parasail_logo.svg -background none -resize 512x512 -gravity center -extent 512x512 "$OUTPUT_DIR/icon@2x.png"
        echo "✓ Created icon@2x.png (512x512)"

        # Create logos (preserve aspect ratio)
        convert parasail_logo.svg -background none -resize x256 "$OUTPUT_DIR/logo.png"
        echo "✓ Created logo.png"

        convert parasail_logo.svg -background none -resize x512 "$OUTPUT_DIR/logo@2x.png"
        echo "✓ Created logo@2x.png"

        echo ""
        echo "✅ All required PNG files have been created!"

    elif command -v inkscape &> /dev/null; then
        echo "Using Inkscape to create PNG files..."

        inkscape parasail_logo.svg --export-type=png --export-filename="$OUTPUT_DIR/icon.png" --export-width=256 --export-height=256 --export-background-opacity=0
        echo "✓ Created icon.png (256x256)"

        inkscape parasail_logo.svg --export-type=png --export-filename="$OUTPUT_DIR/icon@2x.png" --export-width=512 --export-height=512 --export-background-opacity=0
        echo "✓ Created icon@2x.png (512x512)"

        inkscape parasail_logo.svg --export-type=png --export-filename="$OUTPUT_DIR/logo.png" --export-height=256 --export-background-opacity=0
        echo "✓ Created logo.png"

        inkscape parasail_logo.svg --export-type=png --export-filename="$OUTPUT_DIR/logo@2x.png" --export-height=512 --export-background-opacity=0
        echo "✓ Created logo@2x.png"

        echo ""
        echo "✅ All required PNG files have been created!"
    else
        echo "❌ Neither ImageMagick nor Inkscape is installed."
        echo "   Please install one of them to convert SVG to PNG."
    fi
else
    echo "❌ parasail_logo.svg not found in current directory."
    echo ""
    echo "Please download the Parasail logo and save it as 'parasail_logo.svg' in this directory."
    echo "You can get it from:"
    echo "  - https://www.parasail.io (extract from website)"
    echo "  - Contact Parasail directly for official branding assets"
fi

echo ""
echo "Next steps:"
echo "1. Verify the PNG files in $OUTPUT_DIR/"
echo "2. Fork https://github.com/home-assistant/brands"
echo "3. Copy the $OUTPUT_DIR folder to custom_integrations/ in your fork"
echo "4. Submit a pull request"
