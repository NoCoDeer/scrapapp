#!/bin/bash

# Job Scraper - Автоматическая установка
# Использование: curl -sSL https://raw.githubusercontent.com/your-repo/scrapapp/main/install.sh | bash -s your-domain.com

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка аргументов
if [ $# -eq 0 ]; then
    print_error "Необходимо указать домен!"
    echo "Использование: $0 your-domain.com"
    exit 1
fi

DOMAIN=$1
INSTALL_DIR="/opt/scrapapp"
BACKUP_DIR="/opt/scrapapp-backups"

print_info "🚀 Начинаем установку Job Scraper для домена: $DOMAIN"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    print_error "Скрипт должен запускаться от имени root"
    echo "Попробуйте: sudo $0 $DOMAIN"
    exit 1
fi

# Проверка операционной системы
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    print_error "Поддерживается только Linux"
    exit 1
fi

# Функция проверки команды
check_command() {
    if ! command -v $1 &> /dev/null; then
        return 1
    fi
    return 0
}

# Установка зависимостей
install_dependencies() {
    print_info "📦 Установка зависимостей..."
    
    # Настройка неинтерактивного режима
    export DEBIAN_FRONTEND=noninteractive
    export NEEDRESTART_MODE=a
    export NEEDRESTART_SUSPEND=1
    
    # Настройка автоматических ответов для диалогов
    echo 'libc6 libraries/restart-without-asking boolean true' | debconf-set-selections
    echo 'libssl1.1:amd64 libraries/restart-without-asking boolean true' | debconf-set-selections
    
    # Обновление пакетов с неинтерактивными флагами
    apt-get update -qq -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"
    
    # Установка базовых пакетов
    apt-get install -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
        curl wget git unzip software-properties-common apt-transport-https ca-certificates gnupg lsb-release
    
    # Установка Docker
    if ! check_command docker; then
        print_info "🐳 Установка Docker..."
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update -qq -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"
        apt-get install -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
            docker-ce docker-ce-cli containerd.io
        systemctl enable docker
        systemctl start docker
    fi
    
    # Установка Docker Compose
    if ! check_command docker-compose; then
        print_info "🔧 Установка Docker Compose..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
    
    # Установка Nginx
    if ! check_command nginx; then
        print_info "🌐 Установка Nginx..."
        apt-get install -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" nginx
        systemctl enable nginx
    fi
    
    # Установка Certbot
    if ! check_command certbot; then
        print_info "🔒 Установка Certbot..."
        apt-get install -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
            certbot python3-certbot-nginx
    fi
    
    print_success "Все зависимости установлены"
}

# Генерация паролей и ключей
generate_secrets() {
    print_info "🔐 Генерация секретных ключей и паролей..."
    
    # Генерация случайных паролей
    DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    API_KEY=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
    SECRET_KEY=$(openssl rand -base64 64 | tr -d "=+/" | cut -c1-50)
    ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d "=+/" | cut -c1-12)
    
    # Сохранение в файл
    cat > "$INSTALL_DIR/.env" << EOF
# Автоматически сгенерированная конфигурация
# Дата создания: $(date)
# Домен: $DOMAIN

# Основные настройки
ENVIRONMENT=production
DOMAIN=$DOMAIN
SECRET_KEY=$SECRET_KEY
API_KEY=$API_KEY

# База данных
DB_HOST=postgres
DB_PORT=5432
DB_NAME=jobscraper
DB_USER=jobscraper
DB_PASSWORD=$DB_PASSWORD
DATABASE_URL=postgresql://jobscraper:$DB_PASSWORD@postgres:5432/jobscraper

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://redis:6379/0

# Elasticsearch
ELASTICSEARCH_HOST=elasticsearch
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_URL=http://elasticsearch:9200

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# API настройки
API_HOST=0.0.0.0
API_PORT=8000

# Администратор по умолчанию
ADMIN_EMAIL=admin@$DOMAIN
ADMIN_PASSWORD=$ADMIN_PASSWORD

# Scrapy настройки
SCRAPY_SETTINGS_MODULE=scraper.settings

# Мониторинг (опционально)
SENTRY_DSN=
PROMETHEUS_PORT=9090

# Прокси (добавьте свои)
PROXIES=

# Логирование
LOG_LEVEL=INFO
EOF

    print_success "Секретные ключи сгенерированы и сохранены в $INSTALL_DIR/.env"
}

# Скачивание и настройка приложения
setup_application() {
    print_info "📥 Скачивание приложения..."
    
    # Создание директорий
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # Скачивание исходного кода (замените на ваш репозиторий)
    cd "$INSTALL_DIR"
    if [ -d ".git" ]; then
        git pull
    else
        git clone https://github.com/your-repo/scrapapp.git .
    fi
    
    # Генерация секретов
    generate_secrets
    
    # Создание production docker-compose
    cat > "$INSTALL_DIR/docker-compose.prod.yml" << 'EOF'
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    restart: unless-stopped
    networks:
      - scrapapp-network

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - scrapapp-network

  elasticsearch:
    image: elasticsearch:8.8.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    restart: unless-stopped
    networks:
      - scrapapp-network

  api:
    build: ./api
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - ELASTICSEARCH_URL=${ELASTICSEARCH_URL}
      - API_KEY=${API_KEY}
      - SECRET_KEY=${SECRET_KEY}
      - ENVIRONMENT=${ENVIRONMENT}
    depends_on:
      - postgres
      - redis
      - elasticsearch
    restart: unless-stopped
    networks:
      - scrapapp-network

  scraper:
    build: ./scraper
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - ELASTICSEARCH_URL=${ELASTICSEARCH_URL}
      - SCRAPY_SETTINGS_MODULE=${SCRAPY_SETTINGS_MODULE}
      - PROXIES=${PROXIES}
    depends_on:
      - postgres
      - redis
      - api
    restart: unless-stopped
    networks:
      - scrapapp-network

  celery-worker:
    build: ./scraper
    command: celery -A celery_app worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - ELASTICSEARCH_URL=${ELASTICSEARCH_URL}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    networks:
      - scrapapp-network

  celery-beat:
    build: ./scraper
    command: celery -A celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - ELASTICSEARCH_URL=${ELASTICSEARCH_URL}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    networks:
      - scrapapp-network

  admin:
    build: ./admin
    environment:
      - VITE_API_URL=https://${DOMAIN}/api
      - VITE_API_KEY=${API_KEY}
      - VITE_DOMAIN=${DOMAIN}
    restart: unless-stopped
    networks:
      - scrapapp-network

  setup-wizard:
    build: ./setup-wizard
    environment:
      - DOMAIN=${DOMAIN}
      - API_KEY=${API_KEY}
    restart: unless-stopped
    networks:
      - scrapapp-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/sites:/etc/nginx/sites-available
      - /etc/letsencrypt:/etc/letsencrypt
      - nginx_logs:/var/log/nginx
    depends_on:
      - api
      - admin
      - setup-wizard
    restart: unless-stopped
    networks:
      - scrapapp-network

volumes:
  postgres_data:
  redis_data:
  elasticsearch_data:
  nginx_logs:

networks:
  scrapapp-network:
    driver: bridge
EOF

    print_success "Приложение настроено"
}

# Настройка Nginx
setup_nginx() {
    print_info "🌐 Настройка Nginx..."
    
    mkdir -p "$INSTALL_DIR/nginx/sites"
    
    # Основная конфигурация Nginx
    cat > "$INSTALL_DIR/nginx/nginx.conf" << 'EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Логирование
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    access_log /var/log/nginx/access.log main;

    # Основные настройки
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 100M;

    # Gzip сжатие
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/javascript
        application/xml+rss
        application/json;

    # Безопасность
    server_tokens off;
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # Подключение сайтов
    include /etc/nginx/sites-available/*;
}
EOF

    # Конфигурация сайта
    cat > "$INSTALL_DIR/nginx/sites/$DOMAIN.conf" << EOF
# HTTP редирект на HTTPS
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

# HTTPS сервер
server {
    listen 443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;

    # SSL сертификаты (будут настроены позже)
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;

    # Основной сайт (админка)
    location / {
        proxy_pass http://admin:80;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # API
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # WebSocket для real-time обновлений
    location /ws/ {
        proxy_pass http://api:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Мастер установки (только при первом запуске)
    location /setup/ {
        proxy_pass http://setup-wizard:3000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Статические файлы
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

    print_success "Nginx настроен"
}

# Настройка SSL сертификата
setup_ssl() {
    print_info "🔒 Настройка SSL сертификата..."
    
    # Остановка Nginx если запущен
    systemctl stop nginx 2>/dev/null || true
    
    # Получение сертификата
    certbot certonly --standalone --non-interactive --agree-tos --email admin@$DOMAIN -d $DOMAIN -d www.$DOMAIN
    
    if [ $? -eq 0 ]; then
        print_success "SSL сертификат получен"
        
        # Настройка автообновления
        (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet --post-hook 'docker-compose -f $INSTALL_DIR/docker-compose.prod.yml restart nginx'") | crontab -
    else
        print_warning "Не удалось получить SSL сертификат. Будет использоваться HTTP."
        # Создание временной конфигурации без SSL
        sed -i 's/listen 443 ssl http2;/listen 80;/' "$INSTALL_DIR/nginx/sites/$DOMAIN.conf"
        sed -i '/ssl_/d' "$INSTALL_DIR/nginx/sites/$DOMAIN.conf"
    fi
}

# Запуск приложения
start_application() {
    print_info "🚀 Запуск приложения..."
    
    cd "$INSTALL_DIR"
    
    # Сборка и запуск контейнеров
    docker-compose -f docker-compose.prod.yml build
    docker-compose -f docker-compose.prod.yml up -d
    
    # Ожидание запуска сервисов
    print_info "⏳ Ожидание запуска сервисов..."
    sleep 30
    
    # Выполнение миграций
    docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head
    
    # Создание администратора
    docker-compose -f docker-compose.prod.yml exec -T api python -c "
from shared.database import get_db
from shared.models import User
from sqlalchemy.orm import Session
import bcrypt

db = next(get_db())
admin_email = '$ADMIN_EMAIL'
admin_password = '$ADMIN_PASSWORD'

# Проверяем, существует ли администратор
existing_admin = db.query(User).filter(User.email == admin_email).first()
if not existing_admin:
    hashed_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())
    admin_user = User(
        email=admin_email,
        password_hash=hashed_password.decode('utf-8'),
        is_admin=True,
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    print('Администратор создан')
else:
    print('Администратор уже существует')
"
    
    # Настройка Elasticsearch индексов
    docker-compose -f docker-compose.prod.yml exec -T api python -c "
from shared.elasticsearch import setup_elasticsearch
setup_elasticsearch()
print('Elasticsearch настроен')
"
    
    print_success "Приложение запущено"
}

# Создание скриптов управления
create_management_scripts() {
    print_info "📝 Создание скриптов управления..."
    
    mkdir -p "$INSTALL_DIR/scripts"
    
    # Скрипт резервного копирования
    cat > "$INSTALL_DIR/scripts/backup.sh" << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/scrapapp-backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.tar.gz"

echo "Создание резервной копии..."
mkdir -p "$BACKUP_DIR"

# Остановка сервисов
cd /opt/scrapapp
docker-compose -f docker-compose.prod.yml stop

# Создание архива
tar -czf "$BACKUP_FILE" \
    --exclude='*/node_modules' \
    --exclude='*/dist' \
    --exclude='*/build' \
    /opt/scrapapp

# Резервная копия базы данных
docker-compose -f docker-compose.prod.yml exec -T postgres pg_dump -U jobscraper jobscraper > "$BACKUP_DIR/database_$DATE.sql"

# Запуск сервисов
docker-compose -f docker-compose.prod.yml start

echo "Резервная копия создана: $BACKUP_FILE"

# Удаление старых копий (старше 30 дней)
find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +30 -delete
find "$BACKUP_DIR" -name "database_*.sql" -mtime +30 -delete
EOF

    # Скрипт обновления
    cat > "$INSTALL_DIR/scripts/update.sh" << 'EOF'
#!/bin/bash
echo "Обновление приложения..."
cd /opt/scrapapp

# Создание резервной копии
./scripts/backup.sh

# Получение обновлений
git pull

# Пересборка и перезапуск
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Выполнение миграций
docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head

echo "Обновление завершено"
EOF

    # Скрипт мониторинга
    cat > "$INSTALL_DIR/scripts/status.sh" << 'EOF'
#!/bin/bash
echo "=== Статус Job Scraper ==="
cd /opt/scrapapp

echo "Контейнеры:"
docker-compose -f docker-compose.prod.yml ps

echo -e "\nИспользование ресурсов:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

echo -e "\nЛоги (последние 10 строк):"
docker-compose -f docker-compose.prod.yml logs --tail=10
EOF

    # Делаем скрипты исполняемыми
    chmod +x "$INSTALL_DIR/scripts/"*.sh
    
    print_success "Скрипты управления созданы"
}

# Финальная настройка
final_setup() {
    print_info "🎯 Финальная настройка..."
    
    # Создание systemd сервиса для автозапуска
    cat > /etc/systemd/system/scrapapp.service << EOF
[Unit]
Description=Job Scraper Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    systemctl enable scrapapp.service
    
    # Создание алиасов для удобства
    cat >> /root/.bashrc << EOF

# Job Scraper aliases
alias scrapapp-status='cd $INSTALL_DIR && ./scripts/status.sh'
alias scrapapp-backup='cd $INSTALL_DIR && ./scripts/backup.sh'
alias scrapapp-update='cd $INSTALL_DIR && ./scripts/update.sh'
alias scrapapp-logs='cd $INSTALL_DIR && docker-compose -f docker-compose.prod.yml logs -f'
alias scrapapp-restart='cd $INSTALL_DIR && docker-compose -f docker-compose.prod.yml restart'
EOF

    print_success "Финальная настройка завершена"
}

# Вывод информации об установке
show_installation_info() {
    print_success "🎉 Установка завершена успешно!"
    echo
    echo "=== ИНФОРМАЦИЯ ОБ УСТАНОВКЕ ==="
    echo "Домен: https://$DOMAIN"
    echo "Админка: https://$DOMAIN/admin"
    echo "API: https://$DOMAIN/api/docs"
    echo "Мастер настройки: https://$DOMAIN/setup"
    echo
    echo "=== ДАННЫЕ АДМИНИСТРАТОРА ==="
    echo "Email: admin@$DOMAIN"
    echo "Пароль: $ADMIN_PASSWORD"
    echo "API ключ: $API_KEY"
    echo
    echo "=== ПОЛЕЗНЫЕ КОМАНДЫ ==="
    echo "Статус: scrapapp-status"
    echo "Логи: scrapapp-logs"
    echo "Резервная копия: scrapapp-backup"
    echo "Обновление: scrapapp-update"
    echo "Перезапуск: scrapapp-restart"
    echo
    echo "=== ФАЙЛЫ КОНФИГУРАЦИИ ==="
    echo "Основная конфигурация: $INSTALL_DIR/.env"
    echo "Резервные копии: $BACKUP_DIR"
    echo
    print_warning "ВАЖНО: Сохраните данные администратора в безопасном месте!"
    echo
    print_info "Откройте https://$DOMAIN/setup для завершения настройки"
}

# Основная функция установки
main() {
    print_info "🔍 Проверка системы..."
    
    # Проверка подключения к интернету
    if ! ping -c 1 google.com &> /dev/null; then
        print_error "Нет подключения к интернету"
        exit 1
    fi
    
    # Проверка доступности домена
    if ! nslookup $DOMAIN &> /dev/null; then
        print_warning "Домен $DOMAIN не найден в DNS. Убедитесь, что домен настроен правильно."
    fi
    
    # Выполнение установки
    install_dependencies
    setup_application
    setup_nginx
    setup_ssl
    start_application
    create_management_scripts
    final_setup
    show_installation_info
}

# Обработка ошибок
trap 'print_error "Установка прервана"; exit 1' ERR

# Запуск установки
main "$@"
