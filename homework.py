"""Homework-bot.

Telegram-бот, который обращается к API сервиса Яндекс Практикум и узнает статус
вашей домашней работы. Если статус изменился, присылает сообщение.
Также присылает сообщение, если есть ошибки.
"""

import logging
import os
import requests
import sys
import telegram
import time

from dotenv import load_dotenv
from http import HTTPStatus
from json import JSONDecodeError
from requests import HTTPError, RequestException

load_dotenv()

logger = logging.getLogger(__name__)

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

NO_TOKEN_MSG = ('Программа принудительно остановлена.'
                ' Отсутствует обязательная переменная окружения: ')


class UnknownStatusError(Exception):
    """Получен неизвестный статус."""


def check_tokens():
    """Проверяет доступность переменных окружения."""
    token_names = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    no_token_list = []
    for token in token_names:
        if globals()[token] is None:
            no_token_list.append(token)
    if no_token_list:
        logger.critical(f'{NO_TOKEN_MSG}{", ".join(no_token_list)}')
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сообщение {message} в Telegram чат {TELEGRAM_CHAT_ID}'
            f' не отправлено: {telegram_error}!'
        )
    else:
        logger.debug(
            f'Сообщение в Telegram отправлено: {message}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса Яндекс Практикума."""
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT, headers=HEADERS,
                                         params=payload)
    except RequestException as error:
        logger.error(
            f'Ошибка при запросе к API {ENDPOINT} c заголовком {HEADERS}'
            f' и параметрами {payload}: {error}!'
        )
    else:
        if homework_statuses.status_code != HTTPStatus.OK:
            status_code = homework_statuses.status_code
            logger.error(f'Ошибка {status_code}!')
            raise HTTPError(f'Ошибка {status_code}!')
        try:
            return homework_statuses.json()
        except JSONDecodeError as json_error:
            logger.error(f'Ответ API не в формате json: {json_error}')
            raise JSONDecodeError(f'Ответ API не в формате json: {json_error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if type(response) is not dict:
        logger.error('Ответ API не является словарем!')
        raise TypeError('Ответ API не является словарем!')

    keys = ('homeworks', 'current_date')
    for key in keys:
        try:
            response[f'{key}']
        except KeyError:
            logger.error(
                f'В ответе API от {ENDPOINT} на запрос '
                f'с заголовком {HEADERS} отсутствует ключ {key}'
            )
            raise KeyError(
                f'В ответе API от {ENDPOINT} на запрос '
                f'с заголовком {HEADERS} отсутствует ключ {key}'
            )

    homeworks = response['homeworks']
    if type(homeworks) is not list:
        logger.error('Данные по ключу homeworks не являются списком!')
        raise TypeError('Данные по ключу homeworks не являются списком!')

    homework = homeworks[0]
    return homework


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе ee статус."""
    keys = ('homework_name', 'status')
    for key in keys:
        if key not in homework:
            logger.error(
                f'В ответе API от {ENDPOINT} на запрос '
                f'с заголовком {HEADERS} отсутствует ключ {key}'
            )
            raise KeyError(
                f'В ответе API от {ENDPOINT} на запрос '
                f'с заголовком {HEADERS} отсутствует ключ {key}'
            )
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error(f'Неизвестный статус работы: {homework_status}!')
        raise UnknownStatusError(
            f'Неизвестный статус работы: {homework_status}!'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    LAST_STATUS = ''
    ERROR = ''
    if not check_tokens():
        sys.exit(1)
    send_message(bot, 'Запрашиваю статус!')
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            message = parse_status(check_response(response))
            if message != LAST_STATUS:
                send_message(bot, message)
                LAST_STATUS = message
            else:
                logger.debug('Статус работы не изменился.')
        except IndexError:
            logger.debug('Домашнюю работу еще не взяли на ревью!')
        except Exception as error:
            logger.error(error)
            error_message = str(error)
            if error_message != ERROR:
                send_message(bot, error_message)
                ERROR = error_message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(lineno)s - %(message)s',
        handlers=[
            logging.FileHandler('main.log', mode='w', encoding='UTF-8'),
            logging.StreamHandler(stream=sys.stdout)
        ]
    )
    main()
