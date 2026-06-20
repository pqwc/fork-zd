# shared/lib

Утилиты общего назначения (без UI и домена zapret).

## Модули

| Файл | Роль |
|------|------|
| `path_utils.py` | Base path, winws path, AppData, resource paths |
| `version_utils.py` | Semver compare (`compare_versions`, `is_version_newer`) |
| `text_encoding.py` | Чтение файлов с определением кодировки |
| `github_utils.py` | Парсинг URL репозиториев GitHub |
| `app_logging.py` | `setup_logging()` |

## Тесты

`tests/test_version_utils.py` — unit-тесты для `version_utils`.
