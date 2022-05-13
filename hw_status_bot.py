"""
Бот для отслеживания статуса домашней роботы Яндекс Практикум.
"""
import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv

from hw_exceptions import (BadResponseError, DenialOfServiceError,
                           MissingVariableError)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
MY_CHAT_ID = os.getenv('MY_CHAT_ID')
AWESOM_O_TOKEN = os.getenv('AWESOM_O_TOKEN')

VARIABLE_NAMES = ('PRACTICUM_TOKEN', 'AWESOM_O_TOKEN', 'MY_CHAT_ID')

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
RETRY_TIME = 600

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
    'reviewing': 'Работа взята на проверку ревьюером.'
}

BAD_RESPONSE = ('Код ответа API: {}. Параметры запроса: '
                '{url}, {headers}, {params}.')
BOT_LAUNCH_STOPPED = 'Запуск бота остановлен.'
DENIAL_OF_SERVICE = ('Отказ от обслуживания. Ключ: {}. Ошибка: {}. '
                     'Параметры запроса: {url}, {headers}, {params}.')
ERROR_FOUND = 'Ошибка в работе программы: {}.'
INVALID_DATA_TYPE = 'Домашние работы не в виде списка.'
MESSAGE_SENDING_FAILED = 'Сбой при отправке сообщения в Telegram: {}.'
MESSAGE_SENT = 'Сообщение "{}" отправлено в Телеграм.'
MISSED_VARIABLES = ('Отсутствуют обязательные переменные окружения: {}. '
                    'Программа принудительно остановлена.')
MISSING_REQUIRED_KEY = 'В ответе от API-сервиса отсутствует необходимый ключ.'
NO_RESPONSE = ('API-сервис не отвечает: {}. Параметры запроса: '
               '{url}, {headers}, {params}.')
STATUS_CHANGED = 'Изменился статус проверки работы "{}". {}'
STATUSES_NOT_CHANGED = 'Статусы домашних работ не изменились.'
UNEXPECTED_STATUS = 'Неожиданный статус домашней работы: {}.'

current_hw_id = None
last_message = None
last_message_hw_id = None


def check_tokens():
    """Проверка наличия необходимых переменных окружения."""
    missed = [name for name in VARIABLE_NAMES if globals()[name] is None]
    if missed:
        logging.critical(MISSED_VARIABLES.format(missed))
    return not missed


def get_api_answer(timestamp):
    """Отправка запроса о статусе домашней работы к API-сервису."""
    request_params = dict(
        url=ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
    )
    try:
        response = requests.get(**request_params)
    except requests.exceptions.RequestException as error:
        raise ConnectionError(NO_RESPONSE.format(error, **request_params))
    if response.status_code != 200:
        raise BadResponseError(
            BAD_RESPONSE.format(response.status_code, **request_params)
        )
    response_json = response.json()
    for key in ('error', 'code'):
        if key in response_json:
            raise DenialOfServiceError(
                DENIAL_OF_SERVICE.format(
                    key, response_json[key], **request_params
                )
            )
    return response_json


def check_response(response):
    """Проверка корректности ответа на запрос к API-сервису."""
    try:
        homeworks = response['homeworks']
        if not isinstance(homeworks, list):
            raise TypeError(INVALID_DATA_TYPE)
    except KeyError:
        raise KeyError(MISSING_REQUIRED_KEY)
    return homeworks


def parse_status(homework):
    """Получение актуального статуса домашней работы."""
    homework_status = homework['status']
    if homework_status not in VERDICTS:
        raise ValueError(UNEXPECTED_STATUS.format(homework_status))
    return STATUS_CHANGED.format(
        homework['homework_name'], VERDICTS[homework_status]
    )


def send_message(bot, message):
    """Отправка уведомления в указанный чат."""
    global last_message
    global last_message_hw_id
    if last_message == message and last_message_hw_id == current_hw_id:
        return None
    try:
        bot.send_message(
            MY_CHAT_ID, 'Внимание ⚠️ Поступила важная информация 📨'
        )
        bot.send_message(MY_CHAT_ID, message)
        logging.info(MESSAGE_SENT.format(message))
        last_message = message
        last_message_hw_id = current_hw_id
    except Exception as error:
        logging.error(MESSAGE_SENDING_FAILED.format(error))


def main():
    """Основная логика работы бота."""
    global current_hw_id
    if not check_tokens():
        raise MissingVariableError(BOT_LAUNCH_STOPPED)
    bot = telegram.Bot(token=AWESOM_O_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date', timestamp)
            homeworks = check_response(response)
            if homeworks:
                current_hw_id = homeworks[0].get('id')
                send_message(bot, parse_status(homeworks[0]))
            else:
                logging.debug(STATUSES_NOT_CHANGED)
        except Exception as error:
            logging.error(ERROR_FOUND.format(error))
            send_message(bot, ERROR_FOUND.format(error))
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s, %(funcName)s, '
               '%(lineno)s',
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(__file__ + '.log', encoding='utf-8')]
    )
    main()
