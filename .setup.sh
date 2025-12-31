#!/usr/bin/env bash
set -eu
set -o pipefail

PROJECT_ROOT="$(pwd)"
CONTENT_DIR="${PROJECT_ROOT}/content"
SHARE_NAME="thelionsroar-content"

# Try to detect a sensible Samba user
SAMBA_USER="${SUDO_USER:-$USER}"

echo "Project root: ${PROJECT_ROOT}"
echo "Samba user:   ${SAMBA_USER}"
echo "Share name:   ${SHARE_NAME}"
echo

if [[ ! -d "${PROJECT_ROOT}" ]]; then
  echo "Error: project root does not exist: ${PROJECT_ROOT}" >&2
  exit 1
fi

echo "Creating folder structure..."
mkdir -p \
  "${PROJECT_ROOT}/content/news" \
  "${PROJECT_ROOT}/content/events" \
  "${PROJECT_ROOT}/content/magazines" \
  "${PROJECT_ROOT}/content/pages" \
  "${PROJECT_ROOT}/content/widgets" \
  "${PROJECT_ROOT}/templates" \
  "${PROJECT_ROOT}/assets/css" \
  "${PROJECT_ROOT}/assets/js" \
  "${PROJECT_ROOT}/assets/images" \
  "${PROJECT_ROOT}/build" \
  "${PROJECT_ROOT}/build/assets" \
  "${PROJECT_ROOT}/build/data" \
  "${PROJECT_ROOT}/state" \
  "${PROJECT_ROOT}/tools"

# State file placeholder
if [[ ! -f "${PROJECT_ROOT}/state/published.json" ]]; then
  echo "[]" > "${PROJECT_ROOT}/state/published.json"
fi

echo "Setting ownership and permissions..."
# Ensure the chosen user owns the project tree
sudo chown -R "${SAMBA_USER}:${SAMBA_USER}" "${PROJECT_ROOT}"

# Tighten permissions a bit: directories 775, files 664
find "${PROJECT_ROOT}" -type d -exec chmod 775 {} \;
find "${PROJECT_ROOT}" -type f -exec chmod 664 {} \;

# Ensure build is readable by web server
chmod -R a+rX "${PROJECT_ROOT}/build"

echo "Configuring Samba share for ${CONTENT_DIR}..."
sudo mkdir -p /etc/samba/smb.conf.d

CONF_DROPIN="/etc/samba/smb.conf.d/${SHARE_NAME}.conf"
sudo tee "${CONF_DROPIN}" >/dev/null <<EOF
[${SHARE_NAME}]
   comment = The Lion's Roar content (Obsidian vault)
   path = ${CONTENT_DIR}
   browseable = yes
   read only = no
   writable = yes
   valid users = ${SAMBA_USER}
   force user = ${SAMBA_USER}
   create mask = 0664
   directory mask = 0775
EOF

# Ensure smb.conf includes the conf.d directory
SMB_MAIN="/etc/samba/smb.conf"
INCLUDE_LINE="include = /etc/samba/smb.conf.d/*.conf"

if ! grep -qE '^\s*include\s*=\s*/etc/samba/smb\.conf\.d/\*\.conf\s*$' "${SMB_MAIN}"; then
  echo "Adding include line to ${SMB_MAIN} (backup created)..."
  sudo cp "${SMB_MAIN}" "${SMB_MAIN}.bak.$(date +%Y%m%d%H%M%S)"
  # Put include at end to avoid breaking existing config
  echo "" | sudo tee -a "${SMB_MAIN}" >/dev/null
  echo "${INCLUDE_LINE}" | sudo tee -a "${SMB_MAIN}" >/dev/null
fi

echo "Validating Samba config (testparm)..."
sudo testparm -s >/dev/null

echo "Restarting Samba services..."
# Different distros use different unit names, try common ones
if systemctl list-units --type=service | grep -qE '^smbd\.service'; then
  sudo systemctl restart smbd
fi
if systemctl list-units --type=service | grep -qE '^nmbd\.service'; then
  sudo systemctl restart nmbd
fi
if systemctl list-units --type=service | grep -qE '^samba\.service'; then
  sudo systemctl restart samba
fi

echo
echo "Done."
echo "Share created: \\\\$(hostname -I | awk '{print $1}')\\${SHARE_NAME}"
echo "Local path:   ${CONTENT_DIR}"
echo
echo "Next required step:"
echo "  You must add a Samba password for '${SAMBA_USER}' (interactive):"
echo "    sudo smbpasswd -a ${SAMBA_USER}"
echo
echo "If you already have Samba running, this just adds a new share."
