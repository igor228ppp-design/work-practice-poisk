import c104
import time

def on_point_changed(point, previous_info, message):
    """Исправленный коллбэк для приема телеметрии"""
    new_value = message.value
    print(f"📈 [КЛИЕНТ] Перехвачены данные! Точка IOA {point.io_address}: {new_value:.2f}°C")
    return c104.ResponseState.SUCCESS

# 1. Создаем клиента
client = c104.Client()

# 2. Подключаемся к локальному серверу на ПРАВИЛЬНЫЙ порт 2404
connection = client.add_connection(ip="127.0.0.1", port=2404)
station = connection.add_station(common_address=1)

# 3. Подписываемся на точку IOA = 1
point = station.add_point(io_address=1, type=c104.Type.M_ME_NC_1)
point.on_receive(on_point_changed)

print("🔗 КЛИЕНТ: Подключение к серверу...")

# 4. Запускаем клиента (в фоновом потоке библиотеки)
client.start()

# 5. Ожидаем, пока внутреннее состояние соединения перейдет в OPEN
while connection.state != c104.ConnectionState.OPEN:
    time.sleep(0.1)

print("🔗 КЛИЕНТ: Соединение успешно установлено!")

# 6. Запрашиваем общий опрос станции (General Interrogation)
station.interrogation()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Остановка клиента...")
    client.stop()

