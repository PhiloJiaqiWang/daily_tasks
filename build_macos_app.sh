#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Planner"
ENTRY_FILE="app.py"
ICON_PNG="planner_icon.png"
ICON_ICNS="planner_icon.icns"
ICON_ARG=""

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script is for macOS only."
  exit 1
fi

PYINSTALLER_BIN=""
if command -v pyinstaller >/dev/null 2>&1; then
  PYINSTALLER_BIN="pyinstaller"
elif [[ -x ".venv/bin/pyinstaller" ]]; then
  PYINSTALLER_BIN=".venv/bin/pyinstaller"
else
  echo "pyinstaller is not installed."
  echo "Install it with one of these options:"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  python3 -m pip install pyinstaller"
  exit 1
fi

if [[ ! -f "${ICON_ICNS}" ]]; then
  if [[ ! -f "${ICON_PNG}" ]]; then
    echo "Missing icon file. Add ${ICON_PNG} (or ${ICON_ICNS}) in this folder."
    exit 1
  fi

  tmpdir="$(mktemp -d)"
  iconset_dir="${tmpdir}/planner.iconset"
  mkdir -p "${iconset_dir}"

  sips -z 16 16 "${ICON_PNG}" --out "${iconset_dir}/icon_16x16.png" >/dev/null
  sips -z 32 32 "${ICON_PNG}" --out "${iconset_dir}/icon_16x16@2x.png" >/dev/null
  sips -z 32 32 "${ICON_PNG}" --out "${iconset_dir}/icon_32x32.png" >/dev/null
  sips -z 64 64 "${ICON_PNG}" --out "${iconset_dir}/icon_32x32@2x.png" >/dev/null
  sips -z 128 128 "${ICON_PNG}" --out "${iconset_dir}/icon_128x128.png" >/dev/null
  sips -z 256 256 "${ICON_PNG}" --out "${iconset_dir}/icon_128x128@2x.png" >/dev/null
  sips -z 256 256 "${ICON_PNG}" --out "${iconset_dir}/icon_256x256.png" >/dev/null
  sips -z 512 512 "${ICON_PNG}" --out "${iconset_dir}/icon_256x256@2x.png" >/dev/null
  sips -z 512 512 "${ICON_PNG}" --out "${iconset_dir}/icon_512x512.png" >/dev/null
  sips -z 1024 1024 "${ICON_PNG}" --out "${iconset_dir}/icon_512x512@2x.png" >/dev/null
  if iconutil -c icns "${iconset_dir}" -o "${ICON_ICNS}"; then
    echo "Created ${ICON_ICNS} from ${ICON_PNG}"
  else
    echo "iconutil could not create ${ICON_ICNS}; falling back to ${ICON_PNG}."
  fi
  rm -rf "${tmpdir}"
fi

if [[ -f "${ICON_ICNS}" ]]; then
  ICON_ARG="${ICON_ICNS}"
elif [[ -f "${ICON_PNG}" ]]; then
  ICON_ARG="${ICON_PNG}"
else
  echo "No usable icon found."
  exit 1
fi

export PYINSTALLER_CONFIG_DIR="${PWD}/.pyinstaller"

"${PYINSTALLER_BIN}" \
  --noconfirm \
  --clean \
  --windowed \
  --name "${APP_NAME}" \
  --icon "${ICON_ARG}" \
  "${ENTRY_FILE}"

echo "Build complete: dist/${APP_NAME}.app"
