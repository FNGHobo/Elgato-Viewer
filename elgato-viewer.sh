#!/usr/bin/env bash

# --- Configuration ---
ELGATO_PCI="12_00.0" # Default PCI address for the 4K60 Pro MK.2
VIDEO_DEV="/dev/video2" # Default video device

# Auto-detect the audio source based on the PCI address
AUDIO_SOURCE=$(pactl list sources short | grep "$ELGATO_PCI" | awk '{print $2}')

# Auto-detect the user's default audio output (sink)
AUDIO_SINK=$(pactl get-default-sink)

if [ -z "$AUDIO_SOURCE" ]; then
    echo "Error: Could not find Elgato audio source. Is the capture card plugged in?"
    exit 1
fi

if [ -z "$AUDIO_SINK" ]; then
    echo "Error: Could not determine default audio output."
    exit 1
fi

echo "Starting Elgato Viewer..."
echo "Audio Source: $AUDIO_SOURCE"
echo "Audio Output: $AUDIO_SINK"
echo "Video Device: $VIDEO_DEV"
echo "-----------------------------------"

# 1. Start the audio loopback in the background
pw-loopback -m '[ FL FR ]' --capture-props="node.target=\"$AUDIO_SOURCE\"" --playback-props="node.target=\"$AUDIO_SINK\"" &
LOOPBACK_PID=$!

# 2. Ensure the loopback is killed when the script exits (or mpv is closed)
trap "kill $LOOPBACK_PID 2>/dev/null" EXIT

# 3. Start mpv (video only, since audio is handled by loopback)
# If you get a 'device busy' error, uncomment the wireplumber restart line below:
# systemctl --user restart wireplumber

mpv av://v4l2:$VIDEO_DEV --profile=low-latency --title="Elgato Viewer"

# When mpv closes, the script reaches the end and the EXIT trap kills the loopback.
