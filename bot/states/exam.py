from aiogram.fsm.state import State, StatesGroup


class Exam(StatesGroup):
    taking = State()
