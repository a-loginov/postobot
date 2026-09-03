#!/usr/bin/env bash
#
# =============================================================================
#  ПостоБот — развёртывание на сервере my.postobot.su
# =============================================================================
#  Что делает скрипт:
#   1. Проверяет окружение (root, Ubuntu).
#   2. Устанавливает Python 3.12+, pip, venv, Nginx.
#   3. Клонирует/обновляет репозиторий.
#   4. Создаёт виртуальное окружение, устанавливает зависимости.
#   5. Настраивает .env (интерактивно, если ещё не заполнен).
#   6. Создаёт systemd-сервис postobot.
#   7. Настраивает Nginx (reverse proxy на порт админки).
#   8. Запускает сервис.
#
#  Запуск:  sudo bash deploy.sh
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
#  Цвета
# -----------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# -----------------------------------------------------------------------------
#  Параметры
# -----------------------------------------------------------------------------
APP_DIR="/opt/postobot"
REPO_URL="https://github.com/login-ov/postobot.git"
BRANCH="main"
SERVICE_NAME="postobot"
APP_USER="postobot"
ADMIN_PORT="${ADMIN_PORT:-2026}"
DOMAIN="my.postobot.su"

# -----------------------------------------------------------------------------
#  1. Проверка окружения
# -----------------------------------------------------------------------------
[[ "$(id -u)" -eq 0 ]] || fail "Запустите от root: sudo bash deploy.sh"

. /etc/os-release
[[ "$ID" == "ubuntu" ]] || fail "Скрипт рассчитан на Ubuntu (у вас $ID)."
info "ОС: Ubuntu $VERSION_ID"

# -----------------------------------------------------------------------------
#  2. Установка зависимостей
# -----------------------------------------------------------------------------
install_deps() {
    info "Устанавливаю системные пакеты..."
    apt-get update -y
    apt-get install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx
    info "Python: $(python3 --version)"
}

# -----------------------------------------------------------------------------
#  3. Создание пользователя
# -----------------------------------------------------------------------------
create_user() {
    if id "$APP_USER" &>/dev/null; then
        info "Пользователь $APP_USER уже существует."
    else
        info "Создаю пользователя $APP_USER..."
        useradd --system --shell /bin/bash --home-dir "$APP_DIR" "$APP_USER"
    fi
}

# -----------------------------------------------------------------------------
#  4. Клонирование / обновление репозитория
# -----------------------------------------------------------------------------
deploy_code() {
    if [[ -d "$APP_DIR/.git" ]]; then
        info "Обновляю код из репозитория..."
        cd "$APP_DIR"
        git fetch origin "$BRANCH"
        git reset --hard "origin/$BRANCH"
    else
        info "Клонирую репозиторий..."
        rm -rf "$APP_DIR"
        git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
        cd "$APP_DIR"
    fi
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
}

# -----------------------------------------------------------------------------
#  5. Виртуальное окружение и зависимости
# -----------------------------------------------------------------------------
setup_venv() {
    info "Настраиваю виртуальное окружение..."
    cd "$APP_DIR"
    sudo -u "$APP_USER" python3 -m venv .venv
    sudo -u "$APP_USER" .venv/bin/pip install --upgrade pip
    sudo -u "$APP_USER" .venv/bin/pip install -r requirements.txt
    info "Зависимости установлены."
}

# -----------------------------------------------------------------------------
#  6. Настройка .env
# -----------------------------------------------------------------------------
setup_env() {
    cd "$APP_DIR"
    if [[ -f .env ]] && grep -q "BOT_TOKEN=.\+" .env 2>/dev/null; then
        info ".env уже настроен."
        return
    fi

    if [[ -f .env.example ]] && [[ ! -f .env ]]; then
        cp .env.example .env
    fi

    info "Заполните переменные окружения:"
    echo

    read -rp "  BOT_TOKEN: " BOT_TOKEN
    [[ -z "$BOT_TOKEN" ]] && fail "BOT_TOKEN обязателен."

    read -rp "  ADMIN_IDS (через запятую): " ADMIN_IDS
    [[ -z "$ADMIN_IDS" ]] && fail "ADMIN_IDS обязателен."

    read -rp "  ADMIN_PASSWORD: " ADMIN_PASSWORD
    [[ -z "$ADMIN_PASSWORD" ]] && fail "ADMIN_PASSWORD обязателен."

    SECRET_KEY="$(openssl rand -hex 32)"

    cat > .env <<EOF
BOT_TOKEN=${BOT_TOKEN}
ADMIN_IDS=${ADMIN_IDS}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
SECRET_KEY=${SECRET_KEY}
ADMIN_HOST=127.0.0.1
ADMIN_PORT=${ADMIN_PORT}
EOF

    chmod 600 .env
    chown "$APP_USER:$APP_USER" .env
    info ".env создан. SECRET_KEY сгенерирован автоматически."
    info "ВАЖНО: Сохраните SECRET_KEY — он нужен для повторного деплоя."
    echo
    info "SECRET_KEY: ${SECRET_KEY}"
    echo
}

# -----------------------------------------------------------------------------
#  7. Создание директории для БД
# -----------------------------------------------------------------------------
setup_db_dir() {
    cd "$APP_DIR"
    mkdir -p local_db
    chown -R "$APP_USER:$APP_USER" local_db
}

# -----------------------------------------------------------------------------
#  8. Systemd-сервис
# -----------------------------------------------------------------------------
setup_systemd() {
    info "Создаю systemd-сервис ${SERVICE_NAME}..."

    cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=PostoBot — Telegram бот + админ-панель
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/.venv/bin/python main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    info "Сервис создан и включён."
}

# -----------------------------------------------------------------------------
#  9. Nginx reverse proxy
# -----------------------------------------------------------------------------
setup_nginx() {
    info "Настраиваю Nginx..."

    cat > "/etc/nginx/sites-available/${DOMAIN}" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:${ADMIN_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 60s;
        client_max_body_size 10M;
    }
}
EOF

    ln -sf "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
    rm -f /etc/nginx/sites-enabled/default

    nginx -t || fail "Ошибка конфигурации Nginx"
    systemctl reload nginx
    info "Nginx настроен."
}

# -----------------------------------------------------------------------------
#  10. SSL через Let's Encrypt
# -----------------------------------------------------------------------------
setup_ssl() {
    info "Получаю SSL-сертификат для ${DOMAIN}..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@"$DOMAIN" || {
        warn "Не удалось получить сертификат. Попробуйте позже:"
        warn "  sudo certbot --nginx -d ${DOMAIN}"
    }
}

# -----------------------------------------------------------------------------
#  11. Файрвол
# -----------------------------------------------------------------------------
setup_firewall() {
    if ! command -v ufw >/dev/null 2>&1; then
        warn "ufw не установлен, пропускаю."
        return
    fi
    info "Настраиваю файрвол..."
    ufw allow OpenSSH
    ufw allow 'Nginx Full'
    ufw --force enable
}

# -----------------------------------------------------------------------------
#  12. Запуск
# -----------------------------------------------------------------------------
start_service() {
    info "Запускаю ${SERVICE_NAME}..."
    systemctl restart "$SERVICE_NAME"
    sleep 2
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        info "Сервис ${SERVICE_NAME} работает!"
    else
        warn "Сервис не запустился. Проверьте логи:"
        warn "  journalctl -u ${SERVICE_NAME} -f"
    fi
}

# =============================================================================
#  ГЛАВНЫЙ БЛОК
# =============================================================================
install_deps
create_user
deploy_code
setup_venv
setup_env
setup_db_dir
setup_systemd
setup_nginx
setup_ssl
setup_firewall
start_service

echo
info "============================================================"
info "  Развёртывание завершено!"
info "============================================================"
echo
info "Админ-панель: https://${DOMAIN}"
info "Бот: запущен как сервис ${SERVICE_NAME}"
echo
info "Полезные команды:"
info "  systemctl status ${SERVICE_NAME}      — статус"
info "  systemctl restart ${SERVICE_NAME}     — перезапуск"
info "  journalctl -u ${SERVICE_NAME} -f      — логи"
info "  cd ${APP_DIR} && git pull             — обновление кода"
