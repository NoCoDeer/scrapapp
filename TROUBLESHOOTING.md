# Устранение проблем установки Job Scraper

## 🚨 Проблема с зависанием на диалоге обновления ядра

### Симптомы:
```
Newer kernel available                                                    │ 
 │                                                                           │ 
 │ The currently running kernel version is 5.15.0-142-generic which is not   │ 
 │ the expected kernel version 5.15.0-143-generic.                           │ 
 │                                                                           │ 
 │ Restarting the system to load the new kernel will not be handled          │ 
 │ automatically, so you should consider rebooting.                          │ 
 │                                                                           │ 
 │                                  <Ok>                                     │ 
```

### Решение:

#### 1. Немедленное исправление:
```bash
# Подключитесь к серверу в новом терминале
ssh root@your-server

# Найдите зависший процесс
ps aux | grep apt
ps aux | grep dpkg

# Завершите зависшие процессы
sudo pkill -f apt
sudo pkill -f dpkg

# Очистите блокировки
sudo rm /var/lib/dpkg/lock*
sudo rm /var/cache/apt/archives/lock
sudo rm /var/lib/apt/lists/lock

# Исправьте прерванную установку
sudo dpkg --configure -a
```

#### 2. Используйте быстрый скрипт установки:
```bash
curl -sSL https://raw.githubusercontent.com/NoCoDeer/scrapapp/main/quick-install.sh | sudo bash -s scrap.zhigimont.ru
```

#### 3. Альтернативно - ручная установка:
```bash
# Настройка неинтерактивного режима
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

# Установка Docker без системных обновлений
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Клонирование проекта
sudo mkdir -p /opt/scrapapp
cd /opt/scrapapp
sudo git clone https://github.com/NoCoDeer/scrapapp.git .

# Запуск
sudo docker-compose up -d
```

## 🐳 Проблемы с Docker

### Docker не запускается
```bash
# Проверка статуса
sudo systemctl status docker

# Запуск Docker
sudo systemctl start docker
sudo systemctl enable docker

# Проверка версии
docker --version
docker-compose --version
```

### Ошибки прав доступа
```bash
# Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Перезагрузка сессии
newgrp docker

# Или перезагрузка системы
sudo reboot
```

### Недостаточно места на диске
```bash
# Очистка Docker
docker system prune -a

# Проверка использования места
df -h
docker system df
```

## 🌐 Проблемы с сетью

### Порты заняты
```bash
# Проверка занятых портов
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :443

# Остановка конфликтующих сервисов
sudo systemctl stop apache2
sudo systemctl stop nginx
```

### Проблемы с DNS
```bash
# Проверка DNS
nslookup scrap.zhigimont.ru
dig scrap.zhigimont.ru

# Временное решение - добавление в /etc/hosts
echo "YOUR_SERVER_IP scrap.zhigimont.ru" >> /etc/hosts
```

## 🔐 Проблемы с SSL

### Certbot не может получить сертификат
```bash
# Проверка доступности домена
curl -I http://scrap.zhigimont.ru

# Ручное получение сертификата
sudo certbot certonly --standalone -d scrap.zhigimont.ru

# Проверка конфигурации Nginx
sudo nginx -t
```

### Сертификат истек
```bash
# Обновление сертификата
sudo certbot renew

# Перезапуск Nginx
sudo systemctl reload nginx
```

## 📊 Проблемы с базой данных

### PostgreSQL не запускается
```bash
# Проверка логов
docker-compose logs postgres

# Очистка данных (ВНИМАНИЕ: удалит все данные!)
docker-compose down
docker volume rm scrapapp_postgres_data
docker-compose up -d
```

### Ошибки миграций
```bash
# Проверка статуса миграций
docker-compose exec api alembic current

# Принудительное выполнение миграций
docker-compose exec api alembic upgrade head

# Откат миграций
docker-compose exec api alembic downgrade -1
```

## 🔍 Проблемы с Elasticsearch

### Elasticsearch не запускается
```bash
# Увеличение лимита виртуальной памяти
echo 'vm.max_map_count=262144' >> /etc/sysctl.conf
sysctl -p

# Перезапуск контейнера
docker-compose restart elasticsearch
```

### Недостаточно памяти
```bash
# Уменьшение выделенной памяти в docker-compose.yml
# Измените ES_JAVA_OPTS на -Xms256m -Xmx256m
```

## 🕷️ Проблемы со скрапингом

### Пауки не запускаются
```bash
# Проверка логов Celery
docker-compose logs celery-worker

# Ручной запуск паука
docker-compose exec scraper scrapy crawl site1

# Проверка Redis
docker-compose exec redis redis-cli ping
```

### Блокировка сайтами
```bash
# Добавление прокси в .env
PROXIES=http://proxy1:8080,http://proxy2:8080

# Увеличение задержек в settings.py
DOWNLOAD_DELAY = 3
RANDOMIZE_DOWNLOAD_DELAY = 0.5
```

## 📱 Проблемы с фронтендом

### Фронтенд не загружается
```bash
# Проверка логов
docker-compose logs frontend
docker-compose logs admin

# Пересборка фронтенда
docker-compose build frontend admin
docker-compose up -d frontend admin
```

### API недоступен
```bash
# Проверка API
curl http://localhost:8000/health

# Проверка переменных окружения
docker-compose exec api env | grep API
```

## 🔧 Общие команды диагностики

### Проверка статуса всех сервисов
```bash
cd /opt/scrapapp
docker-compose ps
docker-compose logs --tail=50
```

### Мониторинг ресурсов
```bash
# Использование CPU и памяти
docker stats

# Использование диска
df -h
docker system df
```

### Полная переустановка
```bash
# Остановка и удаление всех контейнеров
cd /opt/scrapapp
docker-compose down -v

# Удаление образов
docker rmi $(docker images -q)

# Очистка системы
docker system prune -a

# Повторная установка
curl -sSL https://raw.githubusercontent.com/NoCoDeer/scrapapp/main/quick-install.sh | sudo bash -s scrap.zhigimont.ru
```

## 📞 Получение помощи

### Сбор информации для отчета об ошибке
```bash
# Информация о системе
uname -a
cat /etc/os-release

# Версии Docker
docker --version
docker-compose --version

# Статус сервисов
docker-compose ps
docker-compose logs --tail=100 > logs.txt

# Конфигурация
cat .env (без паролей!)
```

### Контакты для поддержки
- GitHub Issues: https://github.com/NoCoDeer/scrapapp/issues
- Email: support@example.com
- Telegram: @support_bot

## 🚀 Альтернативные методы установки

### Установка через Docker Hub
```bash
# Использование готовых образов
docker run -d --name scrapapp-api jobscraper/api:latest
docker run -d --name scrapapp-admin jobscraper/admin:latest
```

### Установка в Kubernetes
```bash
# Применение манифестов
kubectl apply -f https://raw.githubusercontent.com/NoCoDeer/scrapapp/main/k8s/
```

### Ручная установка без Docker
```bash
# Установка Python зависимостей
pip install -r api/requirements.txt
pip install -r scraper/requirements.txt

# Установка Node.js зависимостей
cd frontend && npm install
cd admin && npm install

# Запуск сервисов
uvicorn api.main:app --host 0.0.0.0 --port 8000
celery -A scraper.celery_app worker
npm run dev
