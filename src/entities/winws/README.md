# entities/winws

Управление runtime zapret (winws.exe).

## Модули

| Файл | Роль |
|------|------|
| `winws_manager.py` | Поиск/остановка процессов winws (psutil) |
| `winws_version.py` | Чтение версии из `service.bat` |

## Пути

Через `shared/lib/path_utils.get_winws_path()`.
