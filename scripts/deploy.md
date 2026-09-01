# ПостоБот — развёртывание production-инфраструктуры

Схема:

```
Telegram
   ↓
🇳🇱 Telegram Gateway (VPS, Нидерланды)
   ↓  VLESS + REALITY (туннель)
🇷🇺 School Server (школа, Россия)
   ↓
FastAPI
   ↓
PostgreSQL
```

> ⚠️ Этот этап не входит в первый этап (локальный бот + SQLite).
> Ниже — инструкция для будущего перехода на production.

---

## 1. Подготовка серверов

Два сервера на Ubuntu 22.04/24.04:

| Сервер            | Роль                                             |
|-------------------|--------------------------------------------------|
| 🇳🇱 Нидерланды     | Telegram Gateway (бот, доступ к Telegram API)    |
| 🇷🇺 Россия (школа) | FastAPI + PostgreSQL + Xray-сервер (VLESS+REALITY)|

Загрузите скрипты из папки `scripts/` на оба сервера.

## 2. Настройка российского сервера

```bash
sudo bash setup_ru_server.sh
```

Скрипт:
- устанавливает Xray, генерирует ключи REALITY и пишет конфиг inbound (порт 443);
- устанавливает PostgreSQL, создаёт базу `postobot` и пользователя `postobot`;
- настраивает ufw (SSH + порт REALITY);
- сохраняет параметры подключения в `/root/postobot_peer_info.txt`.

В конце скрипта будет показан блок с данными: `RU_SERVER_IP`, `REALITY_PORT`,
`UUID`, `PUBLIC_KEY`, `SHORT_ID`, `SNI_DOMAIN`.

В файле `/root/postobot_peer_info.txt` сгенерированные ключи уже заполнены —
впишите в него публичный IP РФ-сервера (`RU_SERVER_IP`).

## 3. Перенос параметров на NL-сервер

С NL-сервера скопируйте файл параметров (или выполните с РФ-сервера):

```bash
# выполняется с NL-сервера:
scp root@<RU_SERVER_IP>:/root/postobot_peer_info.txt /root/postobot_peer_info.txt
```

## 4. Настройка NL-шлюза

```bash
sudo bash setup_nl_server.sh
```

Скрипт:
- читает параметры из `/root/postobot_peer_info.txt` (или спросит вручную);
- устанавливает Xray-клиент и поднимает локальный SOCKS `127.0.0.1:10808`,
  который направляет трафик в туннель VLESS+REALITY на РФ-сервер;
- проверяет туннель.

## 5. Проверка туннеля

```bash
curl --socks5-hostname 127.0.0.1:10808 https://api.telegram.org/
```

Если ответ получен — туннель работает: трафик NL → туннель → РФ-сервер.

## 6. Дальнейшие этапы

- Запустить бота (handlers) на NL-шлюзе так, чтобы обращения к БД шли через
  SOCKS-порт туннеля к FastAPI/PostgreSQL на РФ-сервере.
- На РФ-сервере поднять FastAPI с PostgreSQL вместо SQLite
  (`DATABASE_URL=postgresql+psycopg://...`).
- Заменить `local_db/` на PostgreSQL; бизнес-логика не изменится, т.к.
  handlers → services → repositories → SQLAlchemy.

## Полезные команды

```bash
# статус туннеля Xray на любом из серверов
systemctl status xray

# журнал Xray
journalctl -u xray -f

# перезапуск Xray
systemctl restart xray
```