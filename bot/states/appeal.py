from aiogram.fsm.state import State, StatesGroup


class AppealFlow(StatesGroup):
    waiting_question_number = State()
    waiting_comment = State()


class AppealReview(StatesGroup):
    waiting_new_answer = State()
    waiting_reject_note = State()
