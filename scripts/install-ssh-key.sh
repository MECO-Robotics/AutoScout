#!/usr/bin/env bash
set -euo pipefail

key_path="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"

read -r -p "Remote host [llmhost]: " host
host="${host:-llmhost}"
read -r -p "SSH user [${USER}]: " user
user="${user:-$USER}"
read -r -p "SSH port [22]: " port
port="${port:-22}"

if [[ ! "$port" =~ ^[0-9]+$ ]]; then
  echo "SSH port must be numeric." >&2
  exit 2
fi

if [[ ! -f "$key_path" ]]; then
  echo "No SSH key found at $key_path. Creating one without a passphrase."
  mkdir -p "$(dirname "$key_path")"
  chmod 700 "$(dirname "$key_path")"
  ssh-keygen -t ed25519 -f "$key_path" -N '' -C "autoscout@$(hostname)"
fi

if ! command -v ssh-copy-id >/dev/null 2>&1; then
  echo "ssh-copy-id is required but was not found. Install the openssh-client package." >&2
  exit 1
fi

echo "Installing $key_path.pub on $user@$host:$port."
echo "Enter the remote SSH password when prompted; it is not saved."
ssh-copy-id -i "${key_path}.pub" -p "$port" "$user@$host"

echo "Verifying key-based login."
ssh -o PreferredAuthentications=publickey -o PasswordAuthentication=no \
  -o BatchMode=yes -p "$port" -i "$key_path" "$user@$host" 'printf "SSH key login succeeded on %s\\n" "$(hostname)"'
