"""Homework-bot.

Telegram-бот, который обращается к API сервиса Практикум.Домашкаи узнает статус
вашей домашней работы. Если статус изменился, присылает сообщение.
Также присылает сообщение, если есть ошибки.
"""

import logging
import os
import requests
import sys
import telegram
import time

# from datetime import datetime, timedelta
from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        PRACTICUM_TOKEN: 'PRACTICUM_TOKEN',
        TELEGRAM_TOKEN: 'TELEGRAM_TOKEN',
        TELEGRAM_CHAT_ID: 'TELEGRAM_CHAT_ID',
    }
    all_tokens = True
    message = ('Программа принудительно остановлена.'
               ' Отсутствует обязательная переменная окружения: ')
    for token, token_name in tokens.items():
        if not token or None:
            all_tokens = False
            logger.critical(f'{message}{token_name}')
    return all_tokens


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(
            f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}!')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса Яндекс Практикума."""
    # month_before = datetime.now() - timedelta(days=31) # использовал
    # month_before_unix = int(month_before.timestamp())  #     для
    # payload = {'from_date': month_before_unix}         #   отладки
    payload = {'from date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT, headers=HEADERS,
                                         params=payload)
    except Exception as error:
        logger.error(f'Ошибка при запросе к основному API: {error}!')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        logger.error(f'Ошибка {status_code}!')
        raise Exception(f'Ошибка {status_code}!')
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if type(response) is not dict:
        logger.error('Ответ API не является словарем!')
        raise TypeError('Ответ API не является словарем!')

    keys = ('homeworks', 'current_date')
    for key in keys:
        try:
            response.get(f'{key}')
        except KeyError:
            logger.error(f'В ответе API отсутствует ключ {key}')
            raise KeyError(f'В ответе API отсутствует ключ {key}')

    homeworks = response.get('homeworks')
    if type(homeworks) is not list:
        logger.error('Данные по ключу homeworks не являются списком!')
        raise TypeError('Данные по ключу homeworks не являются списком!')
    try:
        homework = homeworks[0]
    except IndexError:
        logger.error('Список домашних работ пуст!')
        raise IndexError('Список домашних работ пуст!')
    return homework


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе ee статус."""
    keys = ('homework_name', 'status')
    for key in keys:
        if key not in homework:
            logger.error(f'В ответе API отсутствует ключ {key}!')
            raise KeyError(f'В ответе API отсутствует ключ {key}!')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error(f'Неизвестный статус работы: {homework_status}!')
        raise Exception(f'Неизвестный статус работы: {homework_status}!')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    LAST_STATUS = ''
    ERROR = ''
    if not check_tokens():
        sys.exit()
    send_message(bot, 'Запрашиваю статус!')
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            message = parse_status(check_response(response))
            if message != LAST_STATUS:
                send_message(bot, message)
                LAST_STATUS = message
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            logger.error(error)
            error_message = str(error)
            if error_message != ERROR:
                send_message(bot, error_message)
                ERROR = error_message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
