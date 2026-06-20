# pages/main

Главное окно приложения — композиция из 13 mixins.

## Файлы

| Файл | Роль |
|------|------|
| `window.py` | Класс `MainWindow`, MRO mixins |
| `workers.py` | `StartWorker`, `StopWorker`, `BatOutputReader` |
| `mixins/` | Feature-ориентированные mixin-модули |

## Mixins

Каждый mixin отвечает за один аспект UI/логики главного экрана. При добавлении функции:

1. Создайте feature в `features/<name>/`
2. Добавьте или расширьте mixin в `mixins/`
3. Подключите mixin в `window.py` (порядок MRO важен для `closeEvent`, `__init__`)

## Workers

Фоновые потоки запуска/остановки `.bat` — только Qt signals/slots, без прямого UI из worker.
