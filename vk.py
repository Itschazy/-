import logging
from datetime import datetime
from random import randint

from postcards import library, create_postcard

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType


class UserInfo:
    def __init__(self, peer_id, first_name):
        self.peer_id = peer_id
        self.first_name = first_name

        self.card_template = None
        self.card_texts = dict()

        self.templates_shown = set()
        self.query_expected = None

    def reset(self):
        self.card_template = None
        self.card_texts = dict()

        # self.templates_shown = set()
        self.query_expected = None

    @property
    def next_stage(self):
        if len(self.templates_shown) == 0:
            return None
        if self.card_template:
            if len(self.missing_keys) > 0:
                return "query"
            else:
                return "cook"
        else:
            return "template"

    @property
    def missing_keys(self):
        if not self.card_template:
            return None
        query_keys = [stage['id'] for stage in self.card_template['queries']]
        missing_keys = list()
        for key in query_keys:
            if key not in self.card_texts:
                missing_keys.append(key)
        return missing_keys

    @property
    def next_query(self):
        if self.next_stage != "query":
            return None
        else:
            key = self.missing_keys[0]
            return next((stage for stage in self.card_template['queries'] if stage['id'] == key))


class Bot:
    def __init__(self, access_token, group_id):
        self.access_token = access_token
        self.group_id = group_id

        self.launch_moment = datetime.now()
        self.logger = logging.getLogger('app.bot')

        self.logger.info(f"Initializing new shard (group: {self.group_id},"
                         f" token: {self.access_token[:3]})")

        self.session = vk_api.VkApi(token=self.access_token)
        self.vk = self.session.get_api()
        self.uploader = vk_api.VkUpload(self.vk)
        self.longpoll = VkBotLongPoll(self.session, self.group_id)
        self.logger.info("VK API: success")

        self.users = dict()

    def send_message(self, peer_id, text, attachments=None):
        self.logger.debug(f"Sending message to {peer_id}...")

        try:
            return self.vk.messages.send(
                message=text,
                random_id=randint(1000, 9999),
                peer_id=peer_id,
                attachment=attachments or None
            )
        except vk_api.ApiError:
            self.logger.error("Failed to send message.", exc_info=1)
            raise
    
    def get_peer_info(self, peer_id):
        if (int(peer_id) <= 0):
            raise ValueError
        else:
            return self.vk.users.get(
                user_ids=[peer_id]
            )[0]

    def upload_image_pm(self, filename, peer_id):
        self.logger.info(f"Uploading \"{filename}\"")
        pic = self.uploader.photo_messages(
            photos=filename,
            peer_id=peer_id
        )

        return f"photo{pic[0]['owner_id']}_{pic[0]['id']}"

    def event_loop(self):
        for event in self.longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                self.handle_message(event.obj)
            else:
                self.logger.warning(
                    f'Received event of unsupported type: {event.type}'
                )

    def handle_message(self, message):
        self.logger.debug(
            f"Received from {message.peer_id}: {message.text[:30]}"
        )

        if message.peer_id not in self.users:
            user = self.get_peer_info(message.peer_id)
            self.users[message.peer_id] = UserInfo(message.peer_id, user['first_name'])

        info = self.users[message.peer_id]

        if info.next_stage is None:
            self.stage_0(message, info)

        elif info.next_stage == 'template':
            self.stage_template(message, info)

        elif info.next_stage == 'query':
            self.stage_query(message, info)

    def stage_0(self, message, info):
        images = [
            self.upload_image_pm('assets/' + p['preview_file'], message.peer_id)
            for p
            in library['previews']
        ]
        # image = self.upload_image_pm('assets/' + library['template_preview'], message.peer_id)
        self.respond(
            message,
            f"Здравствуйте, {info.first_name}! Выберите шаблон для открытки и отправьте мне его номер.",
            attachments=images
        )
        info.templates_shown.add('*')

    def stage_template(self, message, info):
        try:
            template_no = int(message.text)
            template = next((t for t in library["templates"] if t["index"] == template_no), None)
            if template is None:
                raise ValueError(f'Template #{template_no} not found')

            info.card_template = template
        except (IndexError, ValueError):
            self.respond(
                message,
                "Пожалуйста, отправь номер шаблона. Он указан на картинке."
            )
            return

        query = info.next_query
        info.query_expected = query['id']

        self.respond(
            message,
            query['query_text']
        )
    
    def stage_query(self, message, info):
        if info.query_expected in info.missing_keys:
            info.card_texts[info.query_expected] = message.text
        else:
            self.respond(
                message,
                'Произошла какая-то ошибка! Администратор скоро во всём разберётся...'
            )
        if info.next_stage == 'query':
            query = info.next_query
            info.query_expected = query['id']

            self.respond(
                message,
                query['query_text']
            )
        elif info.next_stage == 'cook':
            self.respond(
                message,
                'Это всё! Рисую открытку, нужно чуть-чуть подождать...'
            )
            create_postcard(info.card_template, info.card_texts)
            image = self.upload_image_pm('assets/temp.png', message.peer_id)

            self.respond(
                message,
                'Твоя открытка готова!',
                attachments=[image]
            )
            info.reset()


    def make_action(self, message, info):
        pass

    def respond(self, message, text, attachments=None):
        self.send_message(
            peer_id=message.peer_id,
            text=text,
            attachments=attachments
        )
