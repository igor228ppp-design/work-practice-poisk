import c104
import random
import time
import subprocess
import re

def get_cpu_temperature_via_sensors() -> float:
    """ Получает реальную температуру процессора, выполняя консольную команду 'sensors' """
    try:
        # Выполняем команду 'sensors' в консоли Linux
        result = subprocess.run(['sensors'], capture_output=True, text=True, check=True)
        
        # Перебираем строки из вывода консоли
        for line in result.stdout.split('\n'):
            # Ищем строки, содержащие типичные маркеры температуры CPU (Core, CPU, Tctl, temp1)
            if any(marker in line for marker in ['Core 0', 'CPU', 'Tctl', 'temp1']):
                # Используем регулярное выражение для поиска числа с плюсом и точкой (например, +45.2°C)
                match = re.search(r'\+(\d+\.\d+)°', line)
                if match:
                    # Преобразуем найденный текст в число с плавающей запятой
                    return float(match.group(1))
                    
        # Если маркеры не найдены, пробуем забрать любое первое попавшееся значение температуры из вывода
        match = re.search(r'\+(\d+\.\d+)°', result.stdout)
        if match:
            return float(match.group(1))
            
        return 0.0
    except Exception as e:
        # Если утилита 'sensors' не установлена или произошла ошибка, возвращаем 0.0
        return 0.0


def on_step_command(point: c104.Point, previous_info: c104.Information, message: c104.IncomingMessage) -> c104.ResponseState:
    """ Обработка входящей пошаговой команды регулирования (телеуправления)
    """
    print("{0} ПОШАГОВАЯ КОМАНДА на IOA: {1}, сообщение: {2}, предыдущее: {3}, текущее: {4}".format(point.type, point.io_address, message, previous_info, point.info))

    if point.value == c104.Step.LOWER:
        return c104.ResponseState.SUCCESS 

    if point.value == c104.Step.HIGHER:
        return c104.ResponseState.SUCCESS 

    return c104.ResponseState.FAILURE


def before_auto_transmit(point: c104.Point) -> None:
    """ Обновление значения точки перед автоматической циклической отправкой
    """
    # Вызываем консольную команду и записываем реальную температуру в точку данных
    point.value = get_cpu_temperature_via_sensors()
    print("{0} ПЕРЕД АВТОМАТИЧЕСКИМ ОТЧЕТОМ на IOA: {1} ТЕМПЕРАТУРА CPU: {2} °C".format(point.type, point.io_address, point.value))


def before_read(point: c104.Point) -> None:
    """ Обновление значения точки перед обработкой запроса на чтение или общего опроса
    """
    # Обновляем значение актуальной температурой при запросе от клиента
    point.value = get_cpu_temperature_via_sensors()
    print("{0} ПЕРЕД ЧТЕНИЕМ или ОБЩИМ ОПРОСОМ на IOA: {1} ТЕМПЕРАТУРА CPU: {2} °C".format(point.type, point.io_address, point.value))


def main():
    # --- 1. Подготовка сервера и контролируемой станции ---
    server = c104.Server()
    station = server.add_station(common_address=47)

    # --- 2. Подготовка точки мониторинга (Телеизмерение температуры) ---
    # ВНИМАНИЕ: Изменен тип на M_ME_TF_1 для корректной передачи дробных чисел (градусов Цельсия)
    point = station.add_point(io_address=11, type=c104.Type.M_ME_TF_1, report_ms=1000)
    
    point.on_before_auto_transmit(callable=before_auto_transmit)
    point.on_before_read(callable=before_read)

    # --- 3. Подготовка точки управления (Телеуправление) ---
    command = station.add_point(io_address=12, type=c104.Type.C_RC_TA_1)
    command.on_receive(callable=on_step_command)

    # --- 4. Запуск сервера и ожидание подключений ---
    server.start()

    while not server.has_active_connections:
        print("Ожидание подключения клиента...")
        time.sleep(1)

    time.sleep(1)

    # --- 5. Основной рабочий цикл (Удержание работы) ---
    c = 0
    while server.has_open_connections and c < 30:
        c += 1
        print("Соединение активно, транслируем данные...")
        time.sleep(1)


if __name__ == "__main__":
    main()
