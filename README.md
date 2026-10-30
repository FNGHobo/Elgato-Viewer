# Elgato Viewer

A simple, low-latency viewer for the **Elgato 4K60 Pro MK.2** on Linux (PipeWire/PulseAudio).

## Features
- Auto-detects the Elgato audio source (via PCI address).
- Routes audio to your **default system output** using `pw-loopback`.
- Displays the video feed using `mpv` with low-latency settings.
- Cleans up the audio loopback automatically when you close the video window.

## Prerequisites
- `mpv`
- `pipewire` and `pipewire-pulse`
- The `sc0710-dkms-git` driver installed (AUR).

## Usage
1. Clone the repo.
2. Run `./elgato-viewer.sh`.
3. Press `q` in the mpv window to close the viewer (and stop the audio loopback).
