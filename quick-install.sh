#!/bin/bash

# Job Scraper - Быстрая установка без системных обновлений
# Использование: curl -sSL https://raw.githubusercontent.com/NoCoDeer/scrapapp/main/quick-install.sh | bash -s your-domain.com

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

print_info "🚀 Быстрая установка Job Scraper для домена: $DOMAIN"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    print_error "Скрипт должен запускаться от имени root"
    echo "Попробуйте: sudo $0 $DOMAIN"
    exit 1
fi

# Функция проверки команды
check_command() {
    if ! command -v $1 &> /dev/null; then
        return 1
    fi
    return 0
}

# Минимальная установка зависимостей
install_minimal_dependencies() {
    print_info "📦 Установка минимальных зависимостей..."
    
    # Настройка неинтерактивного режима
    export DEBIAN_FRONTEND=noninteractive
    export NEEDRESTART_MODE=a
    export NEEDRESTART_SUSPEND=1
    
    # Отключение автоматических обновлений ядра
    echo 'DPkg::Post-Invoke { "echo 0 > /proc/sys/kernel/modules_disabled"; };' > /etc/apt/apt.conf.d/01autoremove-kernels
    
    # Установка только необходимых пакетов без обновления системы
    if ! check_command curl; then
        apt-get install -y --no-upgrade curl
    fi
    
    if ! check_command wget; then
        apt-get install -y --no-upgrade wget
    fi
    
    if ! check_command git; then
        apt-get install -y --no-upgrade git
    fi
    
    # Установка Docker напрямую
    if ! check_command docker; then
        print_info "🐳 Установка Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        systemctl enable docker
        systemctl start docker
        rm get-docker.sh
    fi
    
    # Установка Docker Compose
    if ! check_command docker-compose; then
        print_info "🔧 Установка Docker Compose..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
    
    print_success "Минимальные зависимости установлены"
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
    
    # Скачивание исходного кода
    cd "$INSTALL_DIR"
    if [ -d ".git" ]; then
        git pull
    else
        git clone https://github.com/NoCoDeer/scrapapp.git .
    fi
    
    # Генерация секретов
    generate_secrets
    
    print_success "Приложение настроено"
}

# Настройка простого Nginx
setup_simple_nginx() {
    print_info "🌐 Настройка простого Nginx..."
    
    # Создание простой конфигурации Nginx для HTTP
    mkdir -p "$INSTALL_DIR/nginx"
    
    cat > "$INSTALL_DIR/nginx/nginx.conf" << EOF
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }
    
    upstream admin {
        server admin:80;
    }
    
    server {
        listen 80;
        server_name $DOMAIN;
        
        # Админка
        location / {
            proxy_pass http://admin;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        }
        
        # API
        location /api/ {
            proxy_pass http://api/;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        }
    }
}
EOF

    print_success "Nginx настроен для HTTP"
}

# Запуск приложения
start_application() {
    print_info "🚀 Запуск приложения..."
    
    cd "$INSTALL_DIR"
    
    # Сборка и запуск контейнеров
    docker-compose up -d --build
    
    # Ожидание запуска сервисов
    print_info "⏳ Ожидание запуска сервисов..."
    sleep 45
    
    # Проверка статуса контейнеров
    docker-compose ps
    
    print_success "Приложение запущено"
}

# Создание скриптов управления
create_management_scripts() {
    print_info "📝 Создание скриптов управления..."
    
    mkdir -p "$INSTALL_DIR/scripts"
    
    # Скрипт статуса
    cat > "$INSTALL_DIR/scripts/status.sh" << 'EOF'
#!/bin/bash
echo "=== Статус Job Scraper ==="
cd /opt/scrapapp

echo "Контейнеры:"
docker-compose ps

echo -e "\nЛоги API (последние 10 строк):"
docker-compose logs --tail=10 api

echo -e "\nЛоги Scraper (последние 10 строк):"
docker-compose logs --tail=10 scraper
EOF

    # Скрипт перезапуска
    cat > "$INSTALL_DIR/scripts/restart.sh" << 'EOF'
#!/bin/bash
echo "Перезапуск приложения..."
cd /opt/scrapapp
docker-compose restart
echo "Перезапуск завершен"
EOF

    # Скрипт остановки
    cat > "$INSTALL_DIR/scripts/stop.sh" << 'EOF'
#!/bin/bash
echo "Остановка приложения..."
cd /opt/scrapapp
docker-compose down
echo "Приложение остановлено"
EOF

    # Скрипт запуска
    cat > "$INSTALL_DIR/scripts/start.sh" << 'EOF'
#!/bin/bash
echo "Запуск приложения..."
cd /opt/scrapapp
docker-compose up -d
echo "Приложение запущено"
EOF

    # Делаем скрипты исполняемыми
    chmod +x "$INSTALL_DIR/scripts/"*.sh
    
    # Создание алиасов
    cat >> /root/.bashrc << EOF

# Job Scraper aliases
alias scrapapp-status='cd $INSTALL_DIR && ./scripts/status.sh'
alias scrapapp-restart='cd $INSTALL_DIR && ./scripts/restart.sh'
alias scrapapp-stop='cd $INSTALL_DIR && ./scripts/stop.sh'
alias scrapapp-start='cd $INSTALL_DIR && ./scripts/start.sh'
alias scrapapp-logs='cd $INSTALL_DIR && docker-compose logs -f'
EOF

    print_success "Скрипты управления созданы"
}

# Вывод информации об установке
show_installation_info() {
    print_success "🎉 Быстрая установка завершена!"
    echo
    echo "=== ИНФОРМАЦИЯ ОБ УСТАНОВКЕ ==="
    echo "Домен: http://$DOMAIN (HTTP)"
    echo "Админка: http://$DOMAIN"
    echo "API: http://$DOMAIN/api/docs"
    echo
    echo "=== ДАННЫЕ АДМИНИСТРАТОРА ==="
    echo "Email: admin@$DOMAIN"
    echo "Пароль: $ADMIN_PASSWORD"
    echo "API ключ: $API_KEY"
    echo
    echo "=== ПОЛЕЗНЫЕ КОМАНДЫ ==="
    echo "Статус: scrapapp-status"
    echo "Логи: scrapapp-logs"
    echo "Перезапуск: scrapapp-restart"
    echo "Остановка: scrapapp-stop"
    echo "Запуск: scrapapp-start"
    echo
    echo "=== ФАЙЛЫ КОНФИГУРАЦИИ ==="
    echo "Основная конфигурация: $INSTALL_DIR/.env"
    echo
    print_warning "ВАЖНО: Сохраните данные администратора в безопасном месте!"
    echo
    print_info "Для настройки HTTPS используйте полный скрипт install.sh"
    print_info "Откройте http://$DOMAIN для доступа к системе"
}

# Основная функция установки
main() {
    print_info "🔍 Проверка системы..."
    
    # Проверка подключения к интернету
    if ! ping -c 1 google.com &> /dev/null; then
        print_error "Нет подключения к интернету"
        exit 1
    fi
    
    # Выполнение быстрой установки
    install_minimal_dependencies
    setup_application
    setup_simple_nginx
    start_application
    create_management_scripts
    show_installation_info
}

# Обработка ошибок
trap 'print_error "Установка прервана"; exit 1' ERR

# Запуск установки
main "$@"
