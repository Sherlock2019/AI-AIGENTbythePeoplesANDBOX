#!/bin/bash
set -e

echo "=== Installing Ubuntu Desktop and Chrome Browser ==="
echo "This may take 15-30 minutes and requires several GB of disk space"
echo ""

# Update package list
echo "Updating package list..."
apt-get update -y

# Install Ubuntu Desktop (GNOME)
echo "Installing Ubuntu Desktop (GNOME)..."
export DEBIAN_FRONTEND=noninteractive
apt-get install -y ubuntu-desktop-minimal

# Install X server and display manager
echo "Installing X server and display manager..."
apt-get install -y xorg gdm3

# Install Google Chrome
echo "Installing Google Chrome..."
cd /tmp

# Download Chrome signing key
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -

# Add Chrome repository
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Update package list again
apt-get update -y

# Install Chrome
apt-get install -y google-chrome-stable

echo ""
echo "=== Installation Complete ==="
echo "Ubuntu Desktop and Chrome have been installed."
echo ""
echo "To start the desktop environment:"
echo "  systemctl enable gdm3"
echo "  systemctl start gdm3"
echo ""
echo "Note: You may need to reboot the system for the desktop to work properly."
echo "      If you're on a remote server, you'll need X11 forwarding or VNC."
