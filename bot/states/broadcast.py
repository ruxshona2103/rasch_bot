from aiogram.fsm.state import State, StatesGroup


class Broadcast(StatesGroup):
    waiting_content = State()
    waiting_confirm = State()


class MarketingLogo(StatesGroup):
    waiting_photo = State()
