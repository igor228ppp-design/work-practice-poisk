import c104
import random
import time

# Функция обратного вызова (callback), которая срабатывает при получении неожиданных сообщений от сервера
def con_on_unexpected_message(connection: c104.Connection, message: c104.IncomingMessage, cause: c104.Umc) -> None:
    # Проверяем причину: если это ошибка несоответствия типа данных (Type ID)
    if cause == c104.Umc.MISMATCHED_TYPE_ID :
        # Получаем станцию по ее общему адресу (Common Address)
        station = connection.get_station(message.common_address)
        if station:
            # Получаем точку (point) по ее адресу ввода-вывода (IOA)
            point = station.get_point(message.io_address)
            if point:
                # Выводим предупреждение о конфликте, если тип в сообщении отличается от зарегистрированного
                print("CL] <-in-- КОНФЛИКТ | СЕРВЕР CA {0} сообщает тип IOA {1} как {2}, но он уже зарегистрирован как {3}".format(message.common_address, message.io_address, message.type, point.type))
                return
    # Выводим информацию об отклоненном запросе или ошибке
    print("CL] <-in-- ОТКЛОНЕНО | {1} от СЕРВЕРА CA {0}".format(message.common_address, cause))

def main():
    # --- 1. Подготовка клиента, подключения и станции ---
    
    # Создаем экземпляр клиента протокола МЭК 60870-5-104 (IEC 104)
    client = c104.Client()
    
    # Добавляем новое подключение к серверу (указываем IP и стандартный порт 2404). 
    # Флаг init=c104.Init.ALL означает, что при подключении будут выполнены все процедуры инициализации
    connection = client.add_connection(ip="127.0.0.1", port=2404, init=c104.Init.ALL)
    
    # Назначаем функцию, которая будет обрабатывать непредвиденные сообщения от сервера
    connection.on_unexpected_message(callable=con_on_unexpected_message)
    
    # Добавляем станцию с общим адресом (Common Address) = 47
    station = connection.add_station(common_address=47)

    # --- 2. Подготовка точек данных ---
    
    # Добавляем точку для телеизмерения температуры с адресом IOA = 11. 
    # ВНИМАНИЕ: Изменен тип на M_ME_TF_1 для приема реальных дробных чисел температуры от сервера
    point = station.add_point(io_address=11, type=c104.Type.M_ME_TF_1)

    # Добавляем точку для телеуправления с адресом IOA = 12. 
    # Тип C_RC_TA_1 — команда управления с двумя состояниями (регулирование)
    command = station.add_point(io_address=12, type=c104.Type.C_RC_TA_1)
    
    # Устанавливаем значение команды (например, "увеличить" или "повысить")
    command.value = c104.Step.HIGHER

    # --- 3. Запуск клиента и ожидание соединения ---
    
    # Запускаем фоновый поток клиента для работы с сетью
    client.start()

    # Блокируем выполнение, пока соединение с сервером не перейдет в статус OPEN (установлено)
    while connection.state != c104.ConnectionState.OPEN:
        print("Ожидание подключения к {0}:{1}...".format(connection.ip, connection.port))
        time.sleep(1)

    # Выводим текущее значение точки после инициализации подключения
    print(f"-> ПОСЛЕ ИНИЦИАЛИЗАЦИИ: {point.value}")

    # --- 4. Чтение данных (Запрос опроса) ---
    
    print("Выполняем чтение...")
    
    # Отправляем запрос на чтение (опрос) значения точки с адресом 11
    if point.read():
        print(f"-> УСПЕШНО Получена температура CPU: {point.value} °C") # В случае успеха выводим полученное значение
    else:
        print("-> ОШИБКА при чтении данных")              # Если произошла ошибка запроса

    # --- 5. Отправка команды управления ---
    
    print("Выполняем передачу команды...")
    
    # Передаем команду телеуправления (cause=c104.Cot.ACTIVATION — причина активации)
    if command.transmit(cause=c104.Cot.ACTIVATION):
        print("-> УСПЕШНО Команда отправлена") # Команда успешно отправлена
    else:
        print("-> ОШИБКА при отправке команды") # Ошибка отправки команды

    # Ожидаем 3 секунды, чтобы сервер успел обработать команду
    time.sleep(3)

    # --- 6. Завершение работы ---
    
    print("Выход из программы")


if __name__ == "__main__":
    main()
