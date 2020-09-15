from vk import Bot
import logging
import sys
import json


def setup_logging(level):
    logger = logging.getLogger('app')
    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        fmt='{asctime:>16} | {name:24} | {levelname:8} | {message}', style='{'
    )

    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.setLevel(level)


if __name__ == '__main__':
    setup_logging('DEBUG')
    with open('config.json', 'rt') as f:
        config = json.load(f)

    bot = Bot(
        access_token=config['group_access_token'],
        group_id=config['group_id']
    )
    bot.event_loop()
    
