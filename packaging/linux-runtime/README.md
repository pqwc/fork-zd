# linux-runtime (заглушка)

Эта папка — **не** полный zapret-linux адаптер. Она копируется рядом с собранным GUI
как напоминание: для работы стратегий нужен отдельный каталог с `service.sh`.

## Установка адаптера

1. Клонируйте [zapret-discord-youtube-linux](https://github.com/Sergeydigl3/zapret-discord-youtube-linux):

   ```bash
   git clone https://github.com/Sergeydigl3/zapret-discord-youtube-linux.git ~/zapret-linux
   cd ~/zapret-linux
   ```

2. Следуйте инструкциям в README адаптера (`setup-permissions`, `download-deps`).

3. В ZapretDesktop укажите путь к каталогу с `service.sh`:
   - при первом запуске в диалоге настройки, или
   - **Настройки → Путь к runtime**.

## Почему nfqws не в пакете GUI

Бинарник `nfqws` зависит от архитектуры и обновляется через `service.sh download-deps`.
Пакет ZapretDesktop содержит только интерфейс.

Подробнее: [docs/LINUX_INSTALL.md](../../docs/LINUX_INSTALL.md)
