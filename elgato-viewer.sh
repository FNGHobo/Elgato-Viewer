#!/usr/bin/env bash
# =============================================================================
# elgato-viewer.sh - live viewer for the Elgato 4K60 Pro MK.2 (sc0710 driver)
#
# Video : mpv reads the V4L2 device directly (no recording, mpv plays no audio).
# Audio : pw-loopback sends the card's audio input straight to the headphones/DAC,
#         because mpv's own external-audio path corked (muted) the Elgato stream.
#
# Usage : elgato-viewer.sh           normal live view
#         elgato-viewer.sh --test    driver-only test: no mpv, no audio; prints the
#                                    card's signal format and the measured capture fps
#
# The card has no hardware downscaler: the resolution it captures is whatever the
# console sends. On a Switch 2 set System Settings > Display > TV Resolution to 1080p.
# =============================================================================

# ==========================================
# CONFIGURATION
# ==========================================
# --- Window ---
ALWAYS_ON_TOP="yes"        # yes = keep the mpv window above other windows
FULLSCREEN="yes"           # yes = start fullscreen
VIDEO_ZOOM="0.05"          # mpv --video-zoom (log2 scale): small zoom to crop edge overscan

# --- Capture format (must match what the console is actually sending) ---
TARGET_RESOLUTION="3840x2160"
FRAMERATE="60"

# --- Audio loopback tuning ---
AUDIO_LATENCY_MS=""        # pw-loopback buffer target in ms. Empty = PipeWire default.
                           # Lower = less audio delay but more risk of crackling.
AUDIO_DELAY_SEC="0"        # Extra delay added to the AUDIO only (seconds, decimals ok).
                           # Raise it if you hear the sound BEFORE you see the picture.

# --- Optional display-side experiment ---
SWAPCHAIN_DEPTH=""         # Empty = mpv default (3). Try 1 to reduce display-side latency.

# --- HDR handling ---
HDR_TONEMAP="yes"          # yes = pass mpv tone-mapping flags. They only matter if the
                           # video reaches mpv tagged as HDR; with the driver's default
                           # host tonemap the video is already tagged SDR.

WIDTH=${TARGET_RESOLUTION%x*}
HEIGHT=${TARGET_RESOLUTION#*x}

# ==========================================
# FUNCTIONS
# ==========================================

# find_video_device: print the first /dev/videoN listed under the Elgato entry.
# Needed because Linux renumbers video devices between boots.
find_video_device() {
  v4l2-ctl --list-devices | grep -A 1 "Elgato" | grep "/dev/video" | awk '{print $1}' | head -n 1
}

# find_audio_source: print the PipeWire source node name of the capture card's audio.
find_audio_source() {
  pactl list short sources | grep -i "pci-0000_12_00.0" | awk '{print $2}' | head -n 1
}

# find_audio_sink: print the Sound Blaster G8 sink node name, or the default sink as a fallback.
find_audio_sink() {
  local sink
  sink=$(pactl list short sinks | grep -i "Sound_Blaster_G8_USB-1" | awk '{print $2}' | head -n 1)
  if [ -z "$sink" ]; then sink=$(pactl get-default-sink); fi
  echo "$sink"
}

# show_signal_status: print the signal the driver reports and warn if it is not the
# resolution this script is configured for. It pulls a WIDTHxHEIGHTpRATE token
# (for example 1920x1080p60) out of `sc0710-cli --status`, preferring the "Format:" line,
# and stays quiet about mismatches if it cannot find one.
show_signal_status() {
  local status_text format_line signal
  status_text=$(sc0710-cli --status 2>/dev/null)
  format_line=$(echo "$status_text" | grep -iE 'format[[:space:]]*:' | head -n 1)
  signal=$(echo "${format_line:-$status_text}" | grep -oE '[0-9]{3,4}x[0-9]{3,4}p[0-9]+' | head -n 1)

  if [ -z "$signal" ]; then
    echo "Card signal: could not read it from 'sc0710-cli --status' (run that by hand to check)"
    return
  fi

  echo "Card signal: $signal"
  if [ "$signal" != "${TARGET_RESOLUTION}p${FRAMERATE}" ]; then
    echo "WARNING: card is receiving $signal, but this script is set for ${TARGET_RESOLUTION}p${FRAMERATE}."
    echo "  Set the console output to 1080p (Switch 2: System Settings > Display > TV Resolution),"
    echo "  turn off 120Hz Output, then run this again."
  fi
}

# lock_capture_format: ask the driver for the configured size and YUYV pixel format.
# This only takes effect when it matches the incoming signal.
lock_capture_format() {
  v4l2-ctl -d "$VIDEO_DEV" --set-fmt-video=width="$WIDTH",height="$HEIGHT",pixelformat=YUYV
}

# run_driver_test: stream 300 frames from the card with no player involved.
# If the fps printed here wobbles or drops below the target, the problem is in the
# card/driver/PCIe layer and no mpv setting will fix it.
run_driver_test() {
  lock_capture_format
  echo "Streaming 300 frames straight from the driver (fps is printed about once per second)..."
  v4l2-ctl -d "$VIDEO_DEV" --stream-mmap=32 --stream-count=300 --stream-to=/dev/null
  echo "--- last driver messages ---"
  sudo dmesg | grep -i sc0710 | tail -n 15
  echo "--- driver state (/proc/sc0710-state) ---"
  head -n 40 /proc/sc0710-state 2>/dev/null || echo "(not available)"
}

# start_audio_loopback: route the card's audio to the sink with pw-loopback and
# remember its PID so cleanup can stop it.
start_audio_loopback() {
  local args=(--name elgato-loopback --capture "$AUDIO_SRC" --playback "$AUDIO_SINK")
  if [ -n "$AUDIO_LATENCY_MS" ]; then args+=(--latency "$AUDIO_LATENCY_MS"); fi
  if [ "$AUDIO_DELAY_SEC" != "0" ]; then args+=(--delay "$AUDIO_DELAY_SEC"); fi

  # Stop any loopback left over from a previous run.
  pkill -f "pw-loopback.*elgato-loopback" 2>/dev/null

  pw-loopback "${args[@]}" &
  LOOPBACK_PID=$!
}

# cleanup: stop the audio loopback when the viewer exits or is interrupted.
cleanup() {
  if [ -n "$LOOPBACK_PID" ]; then kill "$LOOPBACK_PID" 2>/dev/null; fi
}

# ==========================================
# SAFETY CHECK
# ==========================================
# Refuse to run as root: pactl and pw-loopback talk to YOUR PipeWire session, which root
# cannot reach, so the audio devices would come back empty. The script calls sudo itself
# only to read dmesg.
if [ "$(id -u)" -eq 0 ]; then
  echo "Run this as your normal user, not with sudo."
  exit 1
fi

# ==========================================
# DEVICE DETECTION
# ==========================================
VIDEO_DEV=$(find_video_device)
AUDIO_SRC=$(find_audio_source)
AUDIO_SINK=$(find_audio_sink)

echo "Video:  $VIDEO_DEV (${WIDTH}x${HEIGHT} @ ${FRAMERATE}fps)"
echo "Input:  $AUDIO_SRC"
echo "Output: $AUDIO_SINK"
show_signal_status

# --test: check the driver on its own, then stop.
if [ "$1" = "--test" ]; then
  run_driver_test
  exit 0
fi

# ==========================================
# START AUDIO + VIDEO
# ==========================================
lock_capture_format
trap cleanup EXIT INT TERM
start_audio_loopback

mkdir -p "$HOME/Pictures/Elgato"   # screenshot destination used by mpv below

MPV_ARGS=(
  "av://v4l2:$VIDEO_DEV"

  # Ask the V4L2 demuxer for raw YUYV at the target size and rate.
  # "-add" appends to the profile's own demuxer options instead of replacing them.
  --demuxer-lavf-o-add="input_format=yuyv422,video_size=${WIDTH}x${HEIGHT},framerate=${FRAMERATE}"

  --no-audio                      # audio is handled by pw-loopback, not mpv
  --profile=low-latency           # built-in profile: no extra audio buffer, 1 decode thread, no interpolation, etc.
  --untimed                       # do not sleep between frames: show each frame as it arrives (live source)
  --cache=no                      # no stream cache for a live capture device
  --demuxer-readahead-secs=0      # do not queue frames ahead of the display
  --hwdec=no                      # raw YUYV needs no decoding, so hardware decode does nothing here
  --vo=gpu-next                   # libplacebo-based renderer
  --video-zoom="$VIDEO_ZOOM"      # see CONFIGURATION
  --screenshot-format=png         # screenshots (key: s) are saved losslessly
  --screenshot-directory="$HOME/Pictures/Elgato"
)

if [ "$HDR_TONEMAP" = "yes" ]; then
  MPV_ARGS+=(
    --tone-mapping=reinhard       # how HDR highlights are compressed to the display's range
    --hdr-compute-peak=yes        # measure the scene peak per frame for tone mapping
    --target-colorspace-hint=no   # do not tell the compositor the output is HDR
  )
fi
if [ -n "$SWAPCHAIN_DEPTH" ]; then MPV_ARGS+=(--swapchain-depth="$SWAPCHAIN_DEPTH"); fi
if [ "$ALWAYS_ON_TOP" = "yes" ]; then MPV_ARGS+=(--ontop); fi
if [ "$FULLSCREEN" = "yes" ]; then MPV_ARGS+=(--fs); fi

mpv "${MPV_ARGS[@]}"
