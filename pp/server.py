import c104
import time
import subprocess
import re
import logging
import signal
import sys

# ─────────────────────────────────────────────
# Настройка логирования
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("iec104_server.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Глобальный флаг для корректного завершения
# ─────────────────────────────────────────────
running: bool = True


def signal_handler(sig, frame) -> None:
    """Обработчик сигналов ОС (Ctrl+C, SIGTERM) для graceful shutdown."""
    global running
    log.info("Получен сигнал завершения (%s). Останавливаем сервер...", sig)
    running = False


# ─────────────────────────────────────────────
# Получение температуры CPU
# ─────────────────────────────────────────────

# Маркеры строк, которые содержат температуру CPU
CPU_TEMP_MARKERS: tuple[str, ...] = ("Core 0", "CPU", "Tctl", "temp1")

# Регулярное выражение для поиска температуры вида «+45.2°C»
TEMP_PATTERN = re.compile(r"\+(\d+\.\d+)°")

# Последнее успешно считанное значение (используется как fallback)
_last_known_temp: float = 0.0


def get_cpu_temperature_via_sensors() -> tuple[float, bool]:
    """
    Считывает температуру CPU через утилиту ``sensors`` (lm-sensors).

    Возвращает:
        Кортеж (температура_в_цельсиях, успех).
        При ошибке возвращает последнее известное значение и False.
    """
    global _last_known_temp

    try:
        result = subprocess.run(
            ["sensors"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except FileNotFoundError:
        log.warning("Утилита 'sensors' не найдена. Установите пакет lm-sensors.")
        return _last_known_temp, False
    except subprocess.TimeoutExpired:
        log.warning("Команда 'sensors' не ответила за 5 секунд.")
        return _last_known_temp, False
    except subprocess.CalledProcessError as exc:
        log.warning("Ошибка выполнения 'sensors': %s", exc)
        return _last_known_temp, False

    # Ищем температуру по приоритетным маркерам
    for line in result.stdout.splitlines():
        if any(marker in line for marker in CPU_TEMP_MARKERS):
            match = TEMP_PATTERN.search(line)
            if match:
                temp = float(match.group(1))
                log.debug("Найдена температура CPU: %.1f °C (строка: %r)", temp, line)
                _last_known_temp = temp
                return temp, True

    # Запасной вариант — первое найденное значение
    match = TEMP_PATTERN.search(result.stdout)
    if match:
        temp = float(match.group(1))
        log.debug("Температура CPU (запасной вариант): %.1f °C", temp)
        _last_known_temp = temp
        return temp, True

    log.warning("Температура CPU не найдена в выводе 'sensors'.")
    return _last_known_temp, False


# ─────────────────────────────────────────────
# Колбэки точек данных
# ─────────────────────────────────────────────

def on_step_command(
    point: c104.Point,
    previous_info: c104.Information,
    message: c104.IncomingMessage,
) -> c104.ResponseState:
    """
    Обработка входящей пошаговой команды регулирования (C_RC_TA_1).

    Поддерживаемые значения:
        * Step.LOWER  — уменьшить уставку
        * Step.HIGHER — увеличить уставку
    """
    log.info(
        "[%s] КОМАНДА на IOA %d | prev=%s | cur=%s | msg=%s",
        point.type,
        point.io_address,
        previous_info,
        point.info,
        message,
    )

    if point.value in (c104.Step.LOWER, c104.Step.HIGHER):
        log.info("Команда %s выполнена успешно.", point.value)
        return c104.ResponseState.SUCCESS

    log.warning("Неизвестное значение команды: %s", point.value)
    return c104.ResponseState.FAILURE


def before_auto_transmit(point: c104.Point) -> None:
    """
    Обновляет значение точки перед автоматической циклической отправкой.
    Вызывается каждые ``report_ms`` миллисекунд.
    """
    temp, ok = get_cpu_temperature_via_sensors()
    point.value = temp

    if not ok:
        log.warning(
            "[%s] АВТО-ОТЧЁТ на IOA %d | ошибка чтения, передаём последнее значение: %.1f °C",
            point.type,
            point.io_address,
            temp,
        )
    else:
        log.info(
            "[%s] АВТО-ОТЧЁТ на IOA %d | температура CPU: %.1f °C",
            point.type,
            point.io_address,
            temp,
        )


def before_read(point: c104.Point) -> None:
    """
    Обновляет значение точки по запросу клиента (READ или общий опрос).
    """
    temp, ok = get_cpu_temperature_via_sensors()
    point.value = temp

    if not ok:
        log.warning(
            "[%s] ЗАПРОС ЧТЕНИЯ на IOA %d | ошибка чтения, передаём последнее значение: %.1f °C",
            point.type,
            point.io_address,
            temp,
        )
    else:
        log.info(
            "[%s] ЗАПРОС ЧТЕНИЯ на IOA %d | температура CPU: %.1f °C",
            point.type,
            point.io_address,
            temp,
        )


# ─────────────────────────────────────────────
# Конфигурация сервера
# ─────────────────────────────────────────────

STATION_COMMON_ADDRESS: int = 47
TEMP_IO_ADDRESS: int        = 11
CMD_IO_ADDRESS: int         = 12
REPORT_INTERVAL_MS: int     = 1000
SERVER_IP: str              = "0.0.0.0"
SERVER_PORT: int            = 2404


# ─────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────

def main() -> None:
    global running

    signal.signal(signal.SIGINT,  signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log.info("=== Запуск IEC 60870-5-104 сервера ===")

    # ── 1. Создание сервера ──────────────────
    server = c104.Server(ip=SERVER_IP, port=SERVER_PORT)

    # ── 2. Создание контролируемой станции ──
    station = server.add_station(common_address=STATION_COMMON_ADDRESS)
    log.info(
        "Станция создана | CA=%d | %s:%d",
        STATION_COMMON_ADDRESS,
        SERVER_IP,
        SERVER_PORT,
    )

    # ── 3. Точка мониторинга (температура) ──
    temp_point: c104.Point = station.add_point(
        io_address=TEMP_IO_ADDRESS,
        type=c104.Type.M_ME_TF_1,
        report_ms=REPORT_INTERVAL_MS,
    )
    temp_point.on_before_auto_transmit(callable=before_auto_transmit)
    temp_point.on_before_read(callable=before_read)
    log.info(
        "Точка температуры | IOA=%d | тип=%s | период=%d мс",
        TEMP_IO_ADDRESS,
        c104.Type.M_ME_TF_1,
        REPORT_INTERVAL_MS,
    )

    # ── 4. Точка управления (пошаговая команда) ──
    cmd_point: c104.Point = station.add_point(
        io_address=CMD_IO_ADDRESS,
        type=c104.Type.C_RC_TA_1,
    )
    cmd_point.on_receive(callable=on_step_command)
    log.info(
        "Точка команды     | IOA=%d | тип=%s",
        CMD_IO_ADDRESS,
        c104.Type.C_RC_TA_1,
    )

    # ── 5. Запуск сервера ────────────────────
    server.start()
    log.info("Сервер запущен. Ожидание подключений на %s:%d...", SERVER_IP, SERVER_PORT)

    # ── 6. Ожидание первого подключения ─────
    while running and not server.has_open_connections:
        log.info("Нет активных клиентов, ждём...")
        time.sleep(2)

    if not running:
        log.info("Завершение до появления клиентов.")
        server.stop()
        return

    # ── 7. Основной цикл ─────────────────────
    log.info("Клиент подключён. Начинаем трансляцию данных.")

    while running:
        if server.has_open_connections:
            log.debug("Соединение активно.")
        else:
            log.warning("Все клиенты отключились. Ожидаем повторного подключения...")
        time.sleep(1)

    # ── 8. Завершение работы ─────────────────
    log.info("Останавливаем сервер IEC 104...")
    server.stop()
    log.info("Сервер остановлен. До свидания!")


if __name__ == "__main__":
    main()
