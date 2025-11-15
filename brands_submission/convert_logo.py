#!/usr/bin/env python3
"""Convert SVG logo to PNG files for Home Assistant brands repository."""

import cairosvg
from pathlib import Path

# Paths
svg_file = Path("parasail_logo.svg")
output_dir = Path("custom_integrations/parasail_conversation")

# Ensure output directory exists
output_dir.mkdir(parents=True, exist_ok=True)

# Define required sizes
conversions = [
    # Icons (square, 1:1 aspect ratio)
    ("icon.png", 256, 256),
    ("icon@2x.png", 512, 512),
    # Logos (landscape - will preserve aspect ratio from source)
    ("logo.png", 512, 256),
    ("logo@2x.png", 1024, 512),
]

print("Converting SVG to PNG files...")
print(f"Source: {svg_file}")
print(f"Output directory: {output_dir}")
print()

for filename, width, height in conversions:
    output_path = output_dir / filename

    try:
        cairosvg.svg2png(
            url=str(svg_file),
            write_to=str(output_path),
            output_width=width,
            output_height=height,
        )
        print(f"✓ Created {filename} ({width}x{height})")
    except Exception as e:
        print(f"✗ Failed to create {filename}: {e}")

print()
print("Conversion complete!")
print(f"Files are in: {output_dir.absolute()}")
