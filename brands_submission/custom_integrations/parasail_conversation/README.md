# Parasail Conversation - Brands Repository Submission

This folder contains the icon and logo files needed for submitting to the Home Assistant brands repository.

## Required Files

Place the following PNG files in this directory:

### Required:
- `icon.png` - 256x256px (square, 1:1 aspect ratio)
- `icon@2x.png` - 512x512px (square, 1:1 aspect ratio)
- `logo.png` - landscape format, shortest side 128-256px
- `logo@2x.png` - landscape format, shortest side 256-512px

### Optional (for dark theme support):
- `dark_icon.png` - 256x256px
- `dark_icon@2x.png` - 512x512px
- `dark_logo.png` - landscape format, shortest side 128-256px
- `dark_logo@2x.png` - landscape format, shortest side 256-512px

## Specifications

All files must be:
- PNG format
- Properly compressed and optimized (lossless preferred)
- Transparent background (preferred)
- Cannot use Home Assistant branded images

## How to Create These Files

### Option 1: Using Parasail's Official Logo
1. Contact Parasail (https://www.parasail.io) to request their official branding assets
2. Convert SVG to PNG at the required resolutions using a tool like:
   - Inkscape (free, command line or GUI)
   - ImageMagick
   - Online converters like CloudConvert

### Option 2: Extract from Website
The Parasail website has their logo at:
- Main logo: `68dca057dfebb8b6760f24a8_logo.svg`
- White logo: `68de1149ae01de1e4b2e15af_parasail%20white%20logo.svg`

### Example Conversion Commands

Using ImageMagick (if you have an SVG):
```bash
# Create icon files (square)
convert parasail_logo.svg -resize 256x256 -gravity center -extent 256x256 icon.png
convert parasail_logo.svg -resize 512x512 -gravity center -extent 512x512 icon@2x.png

# Create logo files (preserve aspect ratio)
convert parasail_logo.svg -resize x256 logo.png
convert parasail_logo.svg -resize x512 logo@2x.png
```

Using Inkscape:
```bash
# Export specific size
inkscape parasail_logo.svg --export-type=png --export-filename=icon.png --export-width=256 --export-height=256
inkscape parasail_logo.svg --export-type=png --export-filename=icon@2x.png --export-width=512 --export-height=512
```

## Next Steps

Once you have all the required PNG files:
1. Fork the Home Assistant brands repository: https://github.com/home-assistant/brands
2. Copy this entire `parasail_conversation` folder to `custom_integrations/` in your fork
3. Submit a pull request
4. Reference this integration: https://github.com/stockhausenj/ha-conversation-parasail

## Validation

Before submitting, verify:
- [ ] All images are PNG format
- [ ] Icons are exactly 256x256 and 512x512 pixels
- [ ] Logos maintain proper aspect ratio
- [ ] Files are optimized/compressed
- [ ] No Home Assistant branding is used
- [ ] Background is transparent (if applicable)
