import os
import logging
import time
import sys

import requests
import telegram
from dotenv import load_dotenv
from http import HTTPStatus

from exceptions import HTTPRequestError, ParseStatusError, RequestExceptionError

load_dotenv()


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
    """Проверяет наличие переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    try:
        logging.debug('Сообщение отправлено')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as e:
        logging.error(f'Ошибка отправки сообщения: {e}')


def get_api_answer(timestamp):
    """Запрос к яндекс-API и возвращение ответа."""
    try:
        timestamp = timestamp or int(time.time())
        params = {'from_date': timestamp}
        logging.info(f'Отправка запроса на {ENDPOINT} с параметрами {params}')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as e:
        message = f'Ошибка в запросе API: {e}'
        raise RequestExceptionError(message)
    if response.status_code != HTTPStatus.OK:
        raise HTTPRequestError(response)
    return response.json()


def check_response(response):
    """Проверка полученного  ответа от Endpoint."""
    if not response:
        message = 'Содержит пустой словарь'
        raise KeyError(message)

    if not isinstance(response, dict):
        message = 'Имеет не корректный тип'
        raise TypeError(message)

    if 'homeworks' not in response:
        message = 'Отсутствие ожидаемых ключей в ответе'
        raise KeyError(message)

    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        message = 'Формат ответа не соответствует'
        raise TypeError(message)
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус работы."""
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)

    if not homework.get('homework_name'):
        homework_name = 'NoName'
        logging.warning('Отсутствует имя домашней работы')
        raise KeyError('В ответе API отсутстует ключ homework_name')
    else:
        homework_name = homework.get('homework_name')

    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Недокументированный статус домашней работы'
        logging.error(message)
        raise KeyError(message)

    if 'status' not in homework:
        message = 'Отсутствует ключ homework_status'
        logging.error(message)
        raise ParseStatusError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(
            'Отсутствует обязательная переменная окружения.\n'
            'Программа принудительно остановлена'
        )
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 1549962000
    status = None
    message = None

    while True:
        try:
            api_answer = get_api_answer(timestamp)
            check_response(api_answer)
            if api_answer['homeworks'] != 0:
                new_status = parse_status(api_answer['homeworks'][0])
                if new_status != status:
                    status = new_status
                    send_message(bot, status)
                else:
                    logging.debug('Статус работы не изменился')
        except Exception as e:
            new_message = f'Сбой в работе прогаммы: {e}'
            logging.error(message)
            if new_message != message:
                message = new_message
                try:
                    send_message(bot, message)
                except Exception as e:
                    logging.error(f'Сбой в работе прогаммы: {e}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        stream=sys.stdout
    )
    main()
