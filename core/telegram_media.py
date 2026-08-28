"""Rasm faylini (document sifatida, istalgan formatda: PNG/JPG va h.k.
yuborilgan) oddiy Telegram photo'ga aylantirib olish uchun umumiy yordamchi.

Nega kerak: agar rasm "file" (document) sifatida kelsa, uning file_id'i
answer_photo/send_photo bilan ishlamaydi (Telegram bu ikkisini alohida turlar
deb hisoblaydi). Shuning uchun bir marta yuklab olib, qayta photo sifatida
yuboramiz — natijadagi file_id esa boshqa joylarda (Exam Mode, marketing
xabari va h.k.) oddiy rasm kabi qayta ishlatilaveradi.
"""

from aiogram.types import BufferedInputFile, Document, Message


async def is_image_document(document: Document) -> bool:
    return (document.mime_type or "").startswith("image/")


async def document_to_photo_file_id(message: Message, document: Document) -> str:
    file_bytes_io = await message.bot.download(document)
    photo_msg = await message.answer_photo(
        photo=BufferedInputFile(file_bytes_io.read(), filename=document.file_name or "rasm.png")
    )
    return photo_msg.photo[-1].file_id
