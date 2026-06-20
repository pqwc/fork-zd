# Исходный код ZapretDesktop (FSD)

Приложение организовано по [Feature-Sliced Design](https://feature-sliced.design/): слои с явными правилами зависимостей.

## Слои (сверху вниз)

| Слой | Путь | Назначение |
|------|------|------------|
| **app** | `app/` | Инициализация, глобальные обработчики (crash dialog) |
| **pages** | `pages/` | Полноэкранные композиции (главное окно, окно тестов) |
| **widgets** | `widgets/` | Переиспользуемые UI-примитивы без бизнес-логики |
| **features** | `features/` | Пользовательские сценарии (диалоги, действия) |
| **entities** | `entities/` | Доменная логика без привязки к конкретному экрану |
| **shared** | `shared/` | Инфраструктура: i18n, утилиты, тема, ассеты |

## Правила импортов

1. Слой может импортировать только **нижележащие** слои и **свои** сегменты.
2. **Запрещено:** `entities` → `features`, `shared` → `entities`, циклы между features.
3. **pages/main/mixins** — композиция features на уровне главного окна; mixins импортируют features и entities, но не другие pages.
4. Все импорты — **абсолютные**: `from src.entities.winws.winws_manager import WinwsManager`.

## Точка входа

`ZapretDesktop.py` (корень репозитория) → `src.pages.main.MainWindow`.

## Документация

- [docs/ARCHITECTURE_FSD.md](../docs/ARCHITECTURE_FSD.md) — карта модулей и миграция
- README в каждой папке слоя — локальные правила и содержимое

## Запуск для разработки

```batch
pip install -r requirements.txt
python ZapretDesktop.py
```

Требуются права администратора Windows.
