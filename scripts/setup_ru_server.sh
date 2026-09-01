#!/usr/bin/env bash
#
# =============================================================================
#  ПостоБот — настройка РОССИЙСКОГО школьного сервера (RU)
# =============================================================================
#  Что делает скрипт:
#   1. Проверяет, что запущен от root на Ubuntu 22.04/24.04.
#   2. Устанавливает Xray (серверная часть VLESS + REALITY).
#   3. Генерирует ключи (uuid, x25519, shortId) и пишет конфиг inbound.
#   4. Устанавливает и настраивает PostgreSQL (база и пользователь postobot).
#   5. Настраивает файрвол (ufw).
#   6. Печатает данные для подключения — их нужно скопировать на NL-сервер.
#
#  Запуск:  sudo bash setup_ru_server.sh
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
#  Цвета и вспомогательные функции
# -----------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# -----------------------------------------------------------------------------
#  1. Проверка окружения
# -----------------------------------------------------------------------------
[[ "$(id -u)" -eq 0 ]] || fail "Запустите скрипт от root: sudo bash setup_ru_server.sh"

. /etc/os-release
if [[ "$ID" != "ubuntu" ]]; then
    fail "Скрипт рассчитан на Ubuntu (у вас $ID)."
fi
info "ОС: Ubuntu $VERSION_ID"

# -----------------------------------------------------------------------------
#  Параметры (можно переопределить через переменные окружения перед запуском)
# -----------------------------------------------------------------------------
REALITY_PORT="${REALITY_PORT:-443}"
SNI_DOMAIN="${SNI_DOMAIN:-www.microsoft.com}"
DEST_DOMAIN="${DEST_DOMAIN:-www.microsoft.com}"

DB_NAME="${DB_NAME:-postobot}"
DB_USER="${DB_USER:-postobot}"
DB_PASSWORD="${DB_PASSWORD:-}"   # если пусто — сгенерируется автоматически

PEER_INFO_FILE="/root/postobot_peer_info.txt"

# -----------------------------------------------------------------------------
#  2. Установка Xray
# -----------------------------------------------------------------------------
install_xray() {
    if command -v xray >/dev/null 2>&1; then
        info "Xray уже установлен ($(xray version | head -n1)). Пропускаю установку."
        return
    fi
    info "Устанавливаю Xray..."
    bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
}

# -----------------------------------------------------------------------------
#  3. Генерация ключей и конфига REALITY (inbound)
# -----------------------------------------------------------------------------
configure_reality_server() {
    info "Генерирую ключи VLESS + REALITY..."

    UUID="$(xray uuid)"
    KEYPAIR="$(xray x25519)"
    PRIVATE_KEY="$(echo "$KEYPAIR" | grep -oP 'Private key: \K.*')"
    PUBLIC_KEY="$(echo "$KEYPAIR" | grep -oP 'Public key: \K.*')"
    SHORT_ID="$(openssl rand -hex 8)"

    CONFIG_FILE="/usr/local/etc/xray/config.json"

    cat > "$CONFIG_FILE" <<EOF
{
  "log": { "loglevel": "warning" },
  "inbounds": [
    {
      "port": ${REALITY_PORT},
      "protocol": "vless",
      "settings": {
        "clients": [ { "id": "${UUID}", "flow": "xtls-rprx-vision" } ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "${DEST_DOMAIN}:443",
          "xver": 0,
          "serverNames": [ "${SNI_DOMAIN}" ],
          "privateKey": "${PRIVATE_KEY}",
          "shortIds": [ "${SHORT_ID}" ]
        }
      },
      "sniffing": { "enabled": true, "destOverride": ["http", "tls", "quic"] }
    }
  ],
  "outbounds": [ { "protocol": "freedom", "tag": "direct" } ]
}
EOF

    systemctl enable xray
    systemctl restart xray
    info "Xray запущен на порту ${REALITY_PORT} (VLESS + REALITY)."
}

# -----------------------------------------------------------------------------
#  4. PostgreSQL: база и пользователь для ПостоБота
# -----------------------------------------------------------------------------
configure_postgres() {
    if ! command -v psql >/dev/null 2>&1; then
        info "Устанавливаю PostgreSQL..."
        apt-get update -y
        apt-get install -y postgresql postgresql-contrib
    else
        info "PostgreSQL уже установлен."
    fi

    info "Инициализирую базу данных '${DB_NAME}' и пользователя '${DB_USER}'..."

    systemctl enable postgresql
    systemctl start postgresql

    if [[ -z "$DB_PASSWORD" ]]; then
        DB_PASSWORD="$(openssl rand -hex 16)"
        warn "Сгенерирован пароль БД: ${DB_PASSWORD}"
    fi

    sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
        CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
    ELSE
        ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
    END IF;
END
\$\$;
SQL

    sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 \
        || sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"

    info "База данных '${DB_NAME}' готова. Пользователь: ${DB_USER}"
}

# -----------------------------------------------------------------------------
#  5. Файрвол
# -----------------------------------------------------------------------------
configure_firewall() {
    if ! command -v ufw >/dev/null 2>&1; then
        warn "Пропускаю настройку ufw (не установлен)."
        return
    fi
    info "Настраиваю файрвол ufw..."
    ufw allow OpenSSH
    ufw allow "${REALITY_PORT}/tcp" comment 'VLESS REALITY'
    ufw --force enable
    ufw status verbose
}

# -----------------------------------------------------------------------------
#  6. Файл с данными для подключения (нужен на NL-сервере)
# -----------------------------------------------------------------------------
write_peer_info() {
    cat > "$PEER_INFO_FILE" <<EOF
# ПостоБот — параметры подключения к российскому серверу (VLESS + REALITY)
# Скопируйте этот файл на NL-сервер, например:
#   scp /root/postobot_peer_info.txt root@NL_IP:/root/postobot_peer_info.txt
RU_SERVER_IP=__FILL_ME__
REALITY_PORT=${REALITY_PORT}
UUID=${UUID}
PUBLIC_KEY=${PUBLIC_KEY}
SHORT_ID=${SHORT_ID}
SNI_DOMAIN=${SNI_DOMAIN}
# Данные PostgreSQL (для будущего этапа FastAPI)
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
EOF
    info "Файл с параметрами записан: ${PEER_INFO_FILE}"
}

# -----------------------------------------------------------------------------
#  Запуск
# -----------------------------------------------------------------------------
install_xray
configure_reality_server
configure_postgres
configure_firewall
write_peer_info

echo
info "============================================================"
info "  Настройка РФ-сервера завершена!"
info "============================================================"
echo
info "Проверка статуса:"
systemctl status xray --no-pager | head -n 5 || true
echo
info "Данные для соединения (также сохранены в ${PEER_INFO_FILE}):"
echo
echo "  RU_SERVER_IP : замените на публичный IP этого сервера"
echo "  REALITY_PORT : ${REALITY_PORT}"
echo "  UUID         : ${UUID}"
echo "  PUBLIC_KEY   : ${PUBLIC_KEY}"
echo "  SHORT_ID     : ${SHORT_ID}"
echo "  SNI_DOMAIN   : ${SNI_DOMAIN}"
echo
info "Теперь скопируйте конфиг на NL-сервер и запустите там setup_nl_server.sh"
echo "  scp ${PEER_INFO_FILE} root@NL_IP:/root/postobot_peer_info.txt"