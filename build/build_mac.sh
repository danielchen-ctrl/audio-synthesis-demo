#!/bin/bash
# Scene Dialogue Demo - macOS Build Script
# PyInstaller packaging for macOS

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
CLEAN_BUILD=false
SKIP_VENV=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN_BUILD=true
            shift
            ;;
        --skip-venv)
            SKIP_VENV=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${CYAN}================================${NC}"
echo -e "${CYAN}Scene Dialogue Demo - macOS Build${NC}"
echo -e "${CYAN}================================${NC}"
echo ""

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Step 1: Clean old build
if [ "$CLEAN_BUILD" = true ]; then
    echo -e "${YELLOW}[1/5] Cleaning old build...${NC}"
    rm -rf dist build/build *.app *.dmg
    echo -e "${GREEN}  Done${NC}"
else
    echo -e "${YELLOW}[1/5] Skip cleaning (use --clean to clean)${NC}"
fi

# Step 2: Setup virtual environment
if [ "$SKIP_VENV" = false ]; then
    echo -e "${YELLOW}[2/5] Checking virtual environment...${NC}"
    
    if [ ! -d ".venv_build" ]; then
        echo -e "${YELLOW}  Creating venv .venv_build...${NC}"
        python3 -m venv .venv_build
        echo -e "${GREEN}  Done${NC}"
    else
        echo -e "${GREEN}  Venv exists${NC}"
    fi
    
    echo -e "${YELLOW}  Activating venv...${NC}"
    source .venv_build/bin/activate
    echo -e "${GREEN}  Done${NC}"
else
    echo -e "${YELLOW}[2/5] Skip venv (using current Python)${NC}"
fi

# Step 3: Install dependencies
echo -e "${YELLOW}[3/5] Installing dependencies...${NC}"
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r requirements.txt --quiet
python3 -m pip install pyinstaller --quiet

# macOS specific: Install pyobjc for better webview support
python3 -m pip install pyobjc-framework-Cocoa pyobjc-framework-WebKit --quiet

echo -e "${GREEN}  Done${NC}"

# Step 4: Run PyInstaller
echo -e "${YELLOW}[4/5] Building application...${NC}"
echo -e "${YELLOW}  Using spec: build/demo_app.spec${NC}"

pyinstaller build/demo_app.spec --clean

if [ $? -ne 0 ]; then
    echo -e "${RED}PyInstaller failed${NC}"
    exit 1
fi
echo -e "${GREEN}  Done${NC}"

# Step 5: Create distribution package
echo -e "${YELLOW}[5/5] Creating distribution package...${NC}"

DIST_DIR="dist/SceneDialogueDemo"
if [ ! -d "$DIST_DIR" ]; then
    echo -e "${RED}Build output directory not found: $DIST_DIR${NC}"
    exit 1
fi

# Check for executable
if [ -f "$DIST_DIR/SceneDialogueDemo" ]; then
    EXE_PATH="$DIST_DIR/SceneDialogueDemo"
elif [ -f "$DIST_DIR.app/Contents/MacOS/SceneDialogueDemo" ]; then
    EXE_PATH="$DIST_DIR.app/Contents/MacOS/SceneDialogueDemo"
else
    echo -e "${RED}Executable not found${NC}"
    exit 1
fi

EXE_SIZE=$(du -m "$EXE_PATH" | cut -f1)
echo -e "${GREEN}  Executable: ${EXE_SIZE} MB${NC}"

TOTAL_SIZE=$(du -sm "$DIST_DIR"* | awk '{sum+=$1} END {print sum}')
echo -e "${GREEN}  Total: ${TOTAL_SIZE} MB${NC}"

# Create DMG (macOS installer)
echo -e "${YELLOW}  Creating DMG installer...${NC}"

DMG_NAME="SceneDialogueDemo_mac_x64.dmg"
APP_NAME="SceneDialogueDemo.app"

# Move or rename to .app if needed
if [ -d "$DIST_DIR" ] && [ ! -d "$APP_NAME" ]; then
    if [ -d "${DIST_DIR}.app" ]; then
        mv "${DIST_DIR}.app" "$APP_NAME"
    else
        # Create .app structure
        mkdir -p "$APP_NAME/Contents/MacOS"
        mkdir -p "$APP_NAME/Contents/Resources"
        
        # Copy executable and resources
        cp -R "$DIST_DIR"/* "$APP_NAME/Contents/MacOS/"
        
        # Create Info.plist
        cat > "$APP_NAME/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>SceneDialogueDemo</string>
    <key>CFBundleIdentifier</key>
    <string>com.demo.scenedialogue</string>
    <key>CFBundleName</key>
    <string>Scene Dialogue Demo</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF
    fi
fi

# Create DMG
if [ -d "$APP_NAME" ]; then
    rm -f "$DMG_NAME"
    
    # Create temporary dmg directory
    DMG_DIR="dmg_temp"
    rm -rf "$DMG_DIR"
    mkdir "$DMG_DIR"
    cp -R "$APP_NAME" "$DMG_DIR/"
    
    # Create symlink to Applications
    ln -s /Applications "$DMG_DIR/Applications"
    
    # Create DMG
    hdiutil create -volname "Scene Dialogue Demo" \
        -srcfolder "$DMG_DIR" \
        -ov -format UDZO \
        "$DMG_NAME"
    
    # Clean up
    rm -rf "$DMG_DIR"
    
    DMG_SIZE=$(du -m "$DMG_NAME" | cut -f1)
    echo -e "${GREEN}  DMG size: ${DMG_SIZE} MB${NC}"
fi

# Also create ZIP as alternative
ZIP_NAME="SceneDialogueDemo_mac_x64.zip"
echo -e "${YELLOW}  Creating ZIP: $ZIP_NAME${NC}"
rm -f "$ZIP_NAME"

if [ -d "$APP_NAME" ]; then
    zip -r -q "$ZIP_NAME" "$APP_NAME"
else
    zip -r -q "$ZIP_NAME" "$DIST_DIR"
fi

ZIP_SIZE=$(du -m "$ZIP_NAME" | cut -f1)
echo -e "${GREEN}  ZIP size: ${ZIP_SIZE} MB${NC}"

# Output results
echo ""
echo -e "${CYAN}================================${NC}"
echo -e "${GREEN}Build successful!${NC}"
echo -e "${CYAN}================================${NC}"
echo ""

if [ -d "$APP_NAME" ]; then
    echo -e "${GREEN}macOS Application: $APP_NAME${NC}"
fi

if [ -f "$DMG_NAME" ]; then
    echo -e "${GREEN}DMG Installer: $DMG_NAME${NC}"
fi

echo -e "${GREEN}ZIP Archive: $ZIP_NAME${NC}"
echo ""
echo -e "${YELLOW}Usage:${NC}"
echo -e "  1. Open $DMG_NAME and drag app to Applications"
echo -e "  2. Or extract $ZIP_NAME and run the app"
echo -e "  3. First launch: Right-click app -> Open (to bypass Gatekeeper)"
echo ""
