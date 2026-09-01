#!/usr/bin/env bash
#
# =============================================================================
#  ПостоБот — настройка сервера-шлюза в НИДЕРЛАНДАХ (NL / Telegram Gateway)
# =============================================================================
#  Что делает скрипт:
#   1. Проверяет, что запущен от root на Ubuntu 22.04/24.04.
#   2. Устанавливает Xray (клиент VLESS + REALITY).
#   3. Берёт параметры соединения с РФ-сервером:
#        - из файла /root/postobot_peer_info.txt (если есть), либо
#        - из интерактивного ввода.
#   4. Пишет конфиг с локальным SOCKS-прокси (127.0.0.1:10808),
#      трафик через который уходит в защищённый туннель на РФ-сервер.
#   5. Проверяет работоспособность туннеля.
#
#  Запуск:  sudo bash setup_nl_server.sh
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
#  Цвета и вспомогательные функции
# -----------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

PEER_INFO_FILE="/root/postobot_peer_info.txt"
SOCKS_PORT="${SOCKS_PORT:-10808}"

# -----------------------------------------------------------------------------
#  1. Проверка окружения
# -----------------------------------------------------------------------------
[[ "$(id -u)" -eq 0 ]] || fail "Запустите скрипт от root: sudo bash setup_nl_server.sh"

. /etc/os-release
[[ "$ID" == "ubuntu" ]] || fail "Скрипт рассчитан на Ubuntu (у вас $ID)."
info "ОС: Ubuntu $VERSION_ID"

# -----------------------------------------------------------------------------
#  2. Установка Xray
# -----------------------------------------------------------------------------
install_xray() {
    if command -v xray >/dev/null 2>&1; then
        info "Xray уже установлен ($(xray version | head -n1)). Пропускаю установку."
        return
    fi
    info "Устанавливаю Xray (клиент)..."
    bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
}

# -----------------------------------------------------------------------------
#  3. Получение параметров соединения с РФ-сервером
# -----------------------------------------------------------------------------
read_params() {
    if [[ -f "$PEER_INFO_FILE" ]]; then
        info "Читаю параметры из ${PEER_INFO_FILE}:"
        # shellcheck disable=SC1090
        . "$PEER_INFO_FILE"
    else
        warn "Файл ${PEER_INFO_FILE} не найден — введите параметры вручную."
    fi

    read_params_var() { # $1 caption, $2 env var, $3 default
        local caption="$1"
        local name="$2"
        local default="${3:-}"
        if [[ -n "${!name:-}" && "${!name:-}" != "__FILL_ME__" ]]; then
            info "  ${caption}: ${!name}"
        else
            read -rp "  ${caption} [${default}]: " "$name"
            : "${!name:?Переменная $name не задана}"
        fi
    }

    read_params_var "IP РФ-сервера" RU_SERVER_IP
    read_params_var "Порт (REALITY_PORT)" REALITY_PORT 443
    read_params_var "UUID" UUID
    read_params_var "Публичный ключ (PUBLIC_KEY)" PUBLIC_KEY
    read_params_var "SHORT_ID" SHORT_ID
    read_params_var "SNI домен (SNI_DOMAIN)" SNI_DOMAIN www.microsoft.com
}

# -----------------------------------------------------------------------------
#  4. Конфигурация клиента (VLESS + REALITY outbound + локальный SOCKS)
# -----------------------------------------------------------------------------
configure_reality_client() {
    info "Пишу клиентский конфиг Xray..."

    CONFIG_FILE="/usr/local/etc/xray/config.json"

    cat > "$CONFIG_FILE" <<EOF
{
  "log": { "loglevel": "warning" },
  "inbounds": [
    {
      "listen": "127.0.0.1",
      "port": ${SOCKS_PORT},
      "protocol": "socks",
      "settings": { "udp": true }
    }
  ],
  "outbounds": [
    {
      "protocol": "vless",
      "settings": {
        "vnext": [
          {
            "address": "${RU_SERVER_IP}",
            "port": ${REALITY_PORT},
            "users": [ { "id": "${UUID}", "flow": "xtls-rprx-vision", "encryption": "none" } ]
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "serverName": "${SNI_DOMAIN}",
          "fingerprint": "chrome",
          "publicKey": "${PUBLIC_KEY}",
          "shortId": "${SHORT_ID}"
        }
      }
    }
  ]
}
EOF

    systemctl enable xray
    systemctl restart xray
    info "Xray-клиент запущен. Локальный SOCKS: 127.0.0.1:${SOCKS_PORT}"
}

# -----------------------------------------------------------------------------
#  5. Файрвол
# -----------------------------------------------------------------------------
configure_firewall() {
    if ! command -v ufw >/dev/null 2>&1; then
        warn "Пропускаю настройку ufw (не установлен)."
        return
    fi
    info "Настраиваю файрвол ufw (оставляю только SSH)..."
    ufw allow OpenSSH
    ufw --force enable
}

# -----------------------------------------------------------------------------
#  6. Тест туннеля
# -----------------------------------------------------------------------------
test_tunnel() {
    info "Проверяю туннель (через SOCKS на ${SOCKS_PORT})..."
    if curl --socks5-hostname "127.0.0.1:${SOCKS_PORT}" \
            --connect-timeout 15 --max-time 20 -fsS https://api.telegram.org/ >/dev/null 2>&1; then
        echo
        echo -e "${GREEN}Туннель работает! Данные через РФ-сервер доставлены.${NC}"
    else
        warn "Туннель не отвечает. Проверьте:"
        warn "  1. IP и ключи совпадают с данными с РФ-сервера."
        warn "  2. На РФ-сервере в ufw открыт порт ${REALITY_PORT}."
        warn "  3. systemctl status xray на обоих серверах."
    fi
}

# -----------------------------------------------------------------------------
#  Запуск
# -----------------------------------------------------------------------------
install_xray
read_params
configure_reality_client
configure_firewall
test_tunnel

echo
info "============================================================"
info "  Настройка NL-сервера завершена!"
info "============================================================"
echo
info "Туннель:  Telegram Gateway -> 127.0.0.1:${SOCKS_PORT} -> VLESS+REALITY -> РФ-сервер"
echo
info "Проверка статуса:"
systemctl status xray --no-pager | head -n 5 || true