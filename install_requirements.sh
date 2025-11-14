#!/bin/bash

# Install Git if not present.
echo "Checking if Git is already installed..."
if ! command -v git >/dev/null; then
  echo "Git was not found. Installing..."
  sudo pacman -S --noconfirm git
else
  echo "Git is already installed!"
fi

# Install Python if not present.
echo "Checking if Python is already installed..."
if ! command -v python >/dev/null; then
  echo "Python was not found. Installing..."
  sudo pacman -S --noconfirm python
else
  echo "Python is already installed!"
fi

# Find where the script is located.
# Source: https://stackoverflow.com/a/246128
echo "Detecting where the script is located..."
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
echo "Detected path: $SCRIPT_DIR"
cd $SCRIPT_DIR

# Set up virtual environment
echo "Setting up virtual environment..."
python -m venv venv
source venv/bin/activate

# Install requirements
echo "Installing requirements in the virtual environment..."
pip install -r requirements.txt

# Deactivate virtual environment
echo "Deactivating virtual environment..."
deactivate

echo "All done!"
