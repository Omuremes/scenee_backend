# CineScope Backend

CineScope — это масштабируемый backend API для мобильного Android-приложения на Kotlin, предназначенного для поиска фильмов, сериалов и локальных мероприятий.

## Архитектура

Backend построен на FastAPI с использованием:
- **PostgreSQL** - основная реляционная база данных
- **Firebase Authentication** - авторизация пользователей
- **MinIO** - S3-compatible object storage для медиафайлов
- **Redis** - кэширование

## Структура проекта

```
app/
├── core/           # Конфигурация, БД, Firebase, Redis
├── models/         # SQLAlchemy модели
├── schemas/        # Pydantic схемы
├── repositories/   # Репозитории для работы с данными
├── services/       # Бизнес-логика
└── routers/        # API endpoints
```

## Запуск

1. **Запустите сервисы инфраструктуры:**
```bash
docker-compose up -d
```

2. **Установите зависимости:**
```bash
pip install -r requirements.txt
```

3. **Создайте базу данных и примените миграции:**
```bash
# Создайте базу данных cinescope в PostgreSQL
# Примените миграции
alembic upgrade head
```

4. **Запустите приложение:**
```bash
uvicorn app.main:app --reload
```

API будет доступно по адресу: http://localhost:8000

## API Endpoints

- `POST /auth/sync` - Синхронизация пользователя с Firebase
- `GET /movies` - Получение списка фильмов
- `GET /movies/{id}` - Детальная информация о фильме
- `GET /events` - Получение списка мероприятий
- `GET /events/{id}` - Детальная информация о мероприятии
- `POST /bookings` - Создание бронирования
- `GET /bookings/me` - Бронирования пользователя
- `POST /favorites` - Добавление в избранное
- `POST /reviews` - Создание отзыва

## Переменные окружения

Скопируйте `.env` и настройте переменные окружения для вашего окружения.

## Разработка

- Используйте async/await для всех операций с БД
- Следуйте принципам чистой архитектуры
- Добавляйте тесты для новых функций
- Используйте Pydantic для валидации данных
