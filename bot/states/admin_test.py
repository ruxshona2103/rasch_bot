from aiogram.fsm.state import State, StatesGroup


class TestCreate(StatesGroup):
    waiting_title = State()
    waiting_closed_count = State()
    waiting_open_count = State()
    waiting_duration = State()
    waiting_price = State()
    waiting_mode = State()
    waiting_method = State()

    # PDF usuli
    waiting_pdf = State()
    waiting_pdf_answer = State()

    # Qo'lda kiritish usuli
    waiting_manual_qtype = State()
    waiting_manual_content = State()
    waiting_manual_options = State()
    waiting_manual_answer = State()
    waiting_manual_next = State()

    waiting_final_confirm = State()
