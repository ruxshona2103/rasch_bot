from aiogram.fsm.state import State, StatesGroup


class PaymentFlow(StatesGroup):
    waiting_receipt = State()


class PaymentReview(StatesGroup):
    waiting_reject_reason = State()


class TestManage(StatesGroup):
    waiting_video_url = State()
    waiting_schedule_time = State()
    waiting_archive_price = State()
