#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_USER="${SUDO_USER:-${USER}}"
ENABLE_NOW=0
PRINT_ONLY=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [--enable-now] [--print]

Options:
  --enable-now   Enable and start all Tiny Film services after installing.
  --print        Print rendered service files instead of installing them.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --enable-now)
      ENABLE_NOW=1
      shift
      ;;
    --print)
      PRINT_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

render_service() {
  local template_path="$1"
  sed \
    -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
    -e "s|__PROJECT_ROOT__|${PROJECT_ROOT}|g" \
    "${template_path}"
}

install_service() {
  local name="$1"
  local template_path="${PROJECT_ROOT}/deploy/${name}.service"
  local service_path="/etc/systemd/system/${name}.service"
  local tmp_file

  tmp_file="$(mktemp)"
  render_service "${template_path}" > "${tmp_file}"
  sudo install -m 0644 "${tmp_file}" "${service_path}"
  rm -f "${tmp_file}"
  echo "Installed ${service_path}"
}

if [[ ${PRINT_ONLY} -eq 1 ]]; then
  for name in tiny-film-web tiny-film-shutter tiny-film-battery; do
    echo "# ${name}.service"
    render_service "${PROJECT_ROOT}/deploy/${name}.service"
    echo
  done
  exit 0
fi

chmod +x \
  "${PROJECT_ROOT}/scripts/run_web.sh" \
  "${PROJECT_ROOT}/scripts/run_shutter.sh" \
  "${PROJECT_ROOT}/scripts/run_battery.sh"

install_service tiny-film-web
install_service tiny-film-shutter
install_service tiny-film-battery
sudo systemctl daemon-reload

if [[ ${ENABLE_NOW} -eq 1 ]]; then
  sudo systemctl enable --now \
    tiny-film-web.service \
    tiny-film-shutter.service \
    tiny-film-battery.service
else
  echo "Enable on boot:"
  echo "  sudo systemctl enable --now tiny-film-web.service tiny-film-shutter.service tiny-film-battery.service"
fi

echo "Web status:"
echo "  sudo systemctl status tiny-film-web.service --no-pager"
echo "Shutter status:"
echo "  sudo systemctl status tiny-film-shutter.service --no-pager"
echo "Battery status:"
echo "  sudo systemctl status tiny-film-battery.service --no-pager"
echo "Logs:"
echo "  sudo journalctl -u tiny-film-web.service -u tiny-film-shutter.service -u tiny-film-battery.service -f"
