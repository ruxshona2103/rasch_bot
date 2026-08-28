from aiogram.fsm.state import State, StatesGroup


class QuestionEdit(StatesGroup):
    waiting_add_qtype = State()
    waiting_add_content = State()
    waiting_add_options = State()
    waiting_add_answer = State()

    waiting_delete_number = State()

    waiting_edit_number = State()
    waiting_edit_qtype = State()
    waiting_edit_content = State()
    waiting_edit_options = State()
    waiting_edit_answer = State()
