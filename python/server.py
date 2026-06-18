import c104
import time
import random

# 1. Создаем сервер МЭК 104 на стандартном порту 2404
server = c104.Server(ip="0.0.0.0", port=2404)

# 2. Добавляем станцию с общим адресом ASDU = 1
station = server.add_station(common_address=1)

# 3. Добавляем точку данных температуры (IOA = 1)
# M_ME_NC_1 — тип данных: короткое число с плавающей точкой
point_temp = station.add_point(io_address=1, type=c104.Type.M_ME_NC_1)


print("🚀 СЕРВЕР: Запуск МЭК 104 на порту 2404...")
server.start()

try:
    while True:
        # Имитируем датчик температуры с небольшими колебаниями
        point_temp.value = 24.5 + random.uniform(-0.5, 0.5)
        print(f"[СЕРВЕР] Обновлено значение IOA 1: {point_temp.value:.2f}°C")
        time.sleep(2)
except KeyboardInterrupt:
    print("Остановка сервера...")
    server.stop()
