#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=()
else
  SUDO=(sudo)
fi

if [[ ! -r /etc/os-release ]]; then
  echo "Cannot identify the operating system." >&2
  exit 1
fi
. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "This installer supports Ubuntu only; detected ${PRETTY_NAME:-unknown}." >&2
  exit 1
fi

echo "Installing NVIDIA video runtime on $(hostname) (${PRETTY_NAME})."
echo "Detected NVIDIA PCI devices:"
lspci | grep -Ei 'NVIDIA.*(VGA|3D|Display)' || {
  echo "No NVIDIA display controller found; refusing to continue." >&2
  exit 1
}

"${SUDO[@]}" apt-get update
"${SUDO[@]}" apt-get install -y ubuntu-drivers-common linux-headers-"$(uname -r)"

echo "Installing Ubuntu's recommended NVIDIA driver."
"${SUDO[@]}" ubuntu-drivers install

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files nvidia-persistenced.service >/dev/null 2>&1; then
  "${SUDO[@]}" systemctl enable nvidia-persistenced.service || true
  "${SUDO[@]}" systemctl start nvidia-persistenced.service || true
fi

echo
echo "Driver installation completed. A reboot is normally required."
if [[ -t 0 ]]; then
  read -r -p "Reboot now? [y/N] " answer
  if [[ "$answer" =~ ^[Yy]$ ]]; then
    exec "${SUDO[@]}" reboot
  fi
fi

echo "Reboot was skipped. After reboot, verify with:"
echo "  nvidia-smi"
echo "Expected: two Quadro P600 devices."
