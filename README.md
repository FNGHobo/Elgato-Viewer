Elgato 4K60 Pro MK.2 Viewer (Linux)
A custom, lightweight PyQt6 frontend for viewing, recording, and capturing screenshots from the Elgato 4K60 Pro MK.2 on Linux. Built to solve the headaches of PipeWire audio routing, HDR tone-mapping, and Wayland window embedding.

https://icon.png/

Features
Native GUI: Built with PyQt6 and libmpv.

4K60 HDR Support: Uses mpv's gpu-next for hardware-accelerated HDR tone mapping.

Seamless Audio: Uses pw-loopback to entirely bypass mpv's audio corking bugs, ensuring perfect A/V sync to your chosen speakers.

Built-in Capture: Take lossless PNG screenshots (Ctrl+S) and record .mkv video (Ctrl+R) directly to your home folders.

Auto-Detection: Automatically finds the Elgato video node and PipeWire audio sources, even if Linux reshuffles the devices.

Wayland Compatible: Forcefully embeds the video into an XWayland window to prevent KDE/Wayland EGL crashes.

🛠️ Dependencies
1. The Driver (sc0710)
You must have the sc0710 open-source driver installed. The easiest way across all distros is to use the official install script from the Nakildias/sc0710 repository:

curl -fsSL https://raw.githubusercontent.com/Nakildias/sc0710/main/scripts/install-sc0710.sh | sudo bash

Arch Linux: Available via AUR (yay -S sc0710-dkms-git).

Ubuntu/Debian/Fedora: The install script above will handle building the DKMS module. Ensure you have dkms and your kernel headers installed.

2. The Viewer App
You will need Python 3, PyQt6, libmpv, PipeWire, and V4L utilities.

Arch Linux:
sudo pacman -S python-pyqt6 python-mpv pipewire v4l-utils alsa-utils

Ubuntu / Debian:
sudo apt update
sudo apt install python3 python3-pyqt6 python3-mpv pipewire v4l-utils alsa-utils

Fedora:
sudo dnf install python3 python3-qt6 python3-mpv pipewire v4l-utils alsa-utils

🚀 Usage
Clone the repository:
git clone https://github.com/FNGHobo/Elgato-Viewer.git
cd Elgato-Viewer

Make the script executable:
chmod +x Elgato-Viewer-GUI.py

Run the app:
./Elgato-Viewer-GUI.py

Keyboard Shortcuts
Ctrl + S : Take a Screenshot (saved to ~/Pictures/Elgato/)

Ctrl + R : Start/Stop Video Recording (saved to ~/Videos/Elgato/)

F11 : Toggle Fullscreen

Ctrl + Q : Quit

(Press Ctrl+O, Enter, Ctrl+X to save and exit).
