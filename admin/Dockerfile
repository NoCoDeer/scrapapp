# Многоэтапная сборка для админ-панели
FROM node:18-alpine AS builder

# Установка рабочей директории
WORKDIR /app

# Копирование package.json и package-lock.json
COPY package*.json ./

# Установка зависимостей
RUN npm ci --only=production

# Копирование исходного кода
COPY . .

# Сборка приложения
RUN npm run build

# Продакшн образ с nginx
FROM nginx:alpine

# Копирование собранного приложения
COPY --from=builder /app/dist /usr/share/nginx/html

# Копирование конфигурации nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Создание пользователя для nginx
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

# Установка прав доступа
RUN chown -R nextjs:nodejs /usr/share/nginx/html && \
    chown -R nextjs:nodejs /var/cache/nginx && \
    chown -R nextjs:nodejs /var/log/nginx && \
    chown -R nextjs:nodejs /etc/nginx/conf.d

# Создание директории для PID файла nginx
RUN touch /var/run/nginx.pid && \
    chown -R nextjs:nodejs /var/run/nginx.pid

# Переключение на непривилегированного пользователя
USER nextjs

# Открытие порта
EXPOSE 3000

# Запуск nginx
CMD ["nginx", "-g", "daemon off;"]
