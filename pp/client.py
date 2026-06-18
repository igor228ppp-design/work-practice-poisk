import c104
import time

# ─────────────────────────────────────────────
# Конфигурация клиента
# ─────────────────────────────────────────────

SERVER_IP: str              = "127.0.0.1"
SERVER_PORT: int            = 2404
STATION_COMMON_ADDRESS: int = 47
TEMP_IO_ADDRESS: int        = 11
CMD_IO_ADDRESS: int         = 12
CONNECT_TIMEOUT_S: int      = 30    # максимальное время ожидания подключения, секунд


# ─────────────────────────────────────────────
# Колбэк: неожиданные сообщения от сервера
# ─────────────────────────────────────────────

def con_on_unexpected_message(
    connection: c104.Connection,
    message: c104.IncomingMessage,
    cause: c104.Umc,
) -> None:
    """Обрабатывает неожиданные или ошибочные сообщения от сервера."""
    if cause == c104.Umc.MISMATCHED_TYPE_ID:
        station = connection.get_station(message.common_address)
        if station:
            point = station.get_point(message.io_address)
            if point:
                print(
                    "[CL] <-in-- КОНФЛИКТ | СЕРВЕР CA {0} сообщает тип IOA {1} "
                    "как {2}, но он уже зарегистрирован как {3}".format(
                        message.common_address,
                        message.io_address,
                        message.type,
                        point.type,
                    )
                )
                return

    print(
        "[CL] <-in-- ОТКЛОНЕНО | {1} от СЕРВЕРА CA {0}".format(
            message.common_address, cause
        )
    )


# ─────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────

def main() -> None:
    # ── 1. Создание клиента и подключения ───
    client = c104.Client()

    connection = client.add_connection(
        ip=SERVER_IP,
        port=SERVER_PORT,
        init=c104.Init.ALL,
    )
    connection.on_unexpected_message(callable=con_on_unexpected_message)

    # ── 2. Добавление станции и точек ───────
    station = connection.add_station(common_address=STATION_COMMON_ADDRESS)

    # Точка температуры (M_ME_TF_1 — float с меткой времени)
    point = station.add_point(io_address=TEMP_IO_ADDRESS, type=c104.Type.M_ME_TF_1)

    # Точка команды (C_RC_TA_1 — пошаговая команда с меткой времени)
    command = station.add_point(io_address=CMD_IO_ADDRESS, type=c104.Type.C_RC_TA_1)
    command.value = c104.Step.HIGHER

    # ── 3. Запуск клиента ───────────────────
    client.start()
    print(f"Подключение к {SERVER_IP}:{SERVER_PORT}...")

    # ── 4. Ожидание установки соединения ────
    waited = 0
    while connection.state != c104.ConnectionState.OPEN:
        if waited >= CONNECT_TIMEOUT_S:
            print(
                f"[ОШИБКА] Не удалось подключиться к {SERVER_IP}:{SERVER_PORT} "
                f"за {CONNECT_TIMEOUT_S} секунд. Завершаем."
            )
            client.stop()
            return
        print(f"Ожидание подключения... ({waited}/{CONNECT_TIMEOUT_S} с)")
        time.sleep(1)
        waited += 1

    print(f"Соединение установлено.")
    print(f"-> ПОСЛЕ ИНИЦИАЛИЗАЦИИ: {point.value}")

    # ── 5. Чтение температуры ───────────────
    print("\nВыполняем чтение температуры...")
    if point.read():
        print(f"-> УСПЕШНО | Температура CPU: {point.value} °C")
    else:
        print("-> ОШИБКА при чтении данных")

    # ── 6. Отправка команды управления ──────
    print("\nВыполняем передачу команды...")
    if command.transmit(cause=c104.Cot.ACTIVATION):
        print(f"-> УСПЕШНО | Команда {command.value} отправлена")
    else:
        print("-> ОШИБКА при отправке команды")

    # Ожидаем подтверждения от сервера
    time.sleep(3)

    # ── 7. Завершение работы ────────────────
    print("\nЗавершение работы клиента...")
    client.stop()
    print("Клиент остановлен. До свидания!")


if __name__ == "__main__":
    main()
