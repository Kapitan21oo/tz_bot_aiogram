import logging
import aiohttp
import asyncio
import time
from aiogram import Bot, Dispatcher, types
from sqlalchemy import create_engine, Column, Integer, String, Float, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker

# Ваш токен телеграм-бота
TOKEN = "6597488638:AAGViKDlZ7a2XeoMCHHUuL3kjbhsubrM8Jk"

# Настройка журнала (логирование)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
CITIES = ["Москва", "Берлин", "Лондон", "Нью-Йорк", "Токио"]
WEATHER_CACHE = {}
DATABASE_URL = "sqlite:///weather_log.db"

# Создание базы данных
Base = declarative_base()


class WeatherLog(Base):
    __tablename__ = 'weather_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String(50), nullable=False)
    temperature = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)
    wind_direction = Column(String(10), nullable=False)
    precipitation = Column(String(20), nullable=False)
    timestamp = Column(Integer, nullable=False)


async def get_weather_data(city: str):
    if city in WEATHER_CACHE and (WEATHER_CACHE[city]["timestamp"] + 600) > time.time():
        return WEATHER_CACHE[city]["data"]

    base_url = f"http://127.0.0.1:8000/weather/?city={city}"
    async with aiohttp.ClientSession() as session:
        async with session.get(base_url) as response:
            if response.status == 200:
                data = await response.json()
                # Кеширование данных о погоде
                WEATHER_CACHE[city] = {"data": data, "timestamp": time.time()}
                return data
            else:
                return None

    return None


async def on_start_command(message: types.Message):
    await message.reply("Введите ваш город:")


async def on_help_command(message: types.Message):
    await message.reply("Доступные команды:\n"
                        "/help - Вывести список команд\n"
                        "/cities - Вывести список доступных городов\n"
                        "/start - Начать работу и получить погоду в выбранном городе")


async def on_cities_command(message: types.Message):
    await message.reply("Доступные города:\n" + "\n".join(CITIES))


async def on_text_message(message: types.Message):
    user_input = message.text.strip().lower()

    if user_input in (city.lower() for city in CITIES):
        city = next(city for city in CITIES if city.lower() == user_input)

        # Вызов функции get_weather_data для получения данных о погоде с сервера Django
        weather_data = await get_weather_data(city)

        if weather_data:
            # Обработка данных о погоде и отправка ответа пользователю
            temperature = weather_data.get("temperature")
            wind_speed = weather_data.get("wind_speed")
            precipitation = weather_data.get("precipitation")

            if temperature is not None and wind_speed is not None and precipitation is not None:
                await message.reply(f"Вы выбрали город: {city}. Погода в этом городе:\n"
                                    f"Температура: {temperature}°C\n"
                                    f"Скорость ветра: {wind_speed} м/с\n"
                                    f"Осадки: {precipitation}")
            else:
                await message.reply("Извините, данные о погоде для этого города недоступны.")
        else:
            await message.reply("Извините, не удалось получить погодные данные для этого города.")
    else:
        await message.reply("Город не найден. Введите другой город.")


async def on_unknown_command(message: types.Message):
    await message.reply("Неизвестная команда. Введите /help для получения списка команд.")


async def save_weather_to_database(city: str, weather_data: dict):
    try:
        engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)
        session = Session()

        weather_log = WeatherLog(city=city,
                                 temperature=weather_data["temperature"],
                                 wind_speed=weather_data["wind_speed"],
                                 wind_direction=weather_data["wind_direction"],
                                 precipitation=weather_data["precipitation"],
                                 timestamp=int(time.time()))
        session.add(weather_log)
        session.commit()

    except Exception as e:
        logger.error("Ошибка сохранения данных о погоде в базу данных: %s", e)
        session.rollback()

    finally:
        session.close()


async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher(bot)

    dp.register_message_handler(on_start_command, commands="start")
    dp.register_message_handler(on_help_command, commands="help")
    dp.register_message_handler(on_cities_command, commands="cities")
    dp.register_message_handler(on_text_message, content_types=types.ContentType.TEXT)
    dp.register_message_handler(on_unknown_command)

    # Запуск бота
    await dp.start_polling()


if __name__ == '__main__':
    asyncio.run(main())
