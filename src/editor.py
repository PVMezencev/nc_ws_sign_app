import os

import fitz
from pdfrw import PdfReader, PdfWriter, PageMerge
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4, A3, landscape
import io


def create_image_reader(img_buffer):
    return ImageReader(img_buffer)

def convert_scanned_pdf_to_pdf(input_pdf_data, dpi=150):
    """
    Конвертирует сканированный PDF через изображение с улучшенными настройками

    Args:
        input_pdf_data: данные PDF в виде bytes
        dpi: разрешение для конвертации (по умолчанию 150)

    Returns:
        bytes: конвертированные данные PDF
    """
    try:
        # Открываем исходный PDF
        doc = fitz.open(stream=input_pdf_data, filetype="pdf")

        # Создаем новый PDF документ
        pdf_writer = fitz.open()

        # Конвертируем каждую страницу
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Создаем изображение страницы с заданным DPI
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))  # 300 DPI

            # Создаем новую страницу с такими же размерами
            new_page = pdf_writer.new_page(width=page.rect.width, height=page.rect.height)

            # Вставляем изображение как картинку
            img_data = pix.tobytes("png")  # Используем PNG для лучшего качества
            img_rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
            new_page.insert_image(img_rect, stream=img_data)

        # Получаем результат
        pdf_bytes = pdf_writer.tobytes(deflate=True, garbage=4)

        # Закрываем документы
        doc.close()
        pdf_writer.close()

        return pdf_bytes

    except Exception as e:
        print(f"Ошибка при конвертации PDF: {e}")
        # В случае ошибки возвращаем оригинальные данные
        return input_pdf_data

def add_png_pdfrw(image, position, input_pdf=None, output_pdf=None, input_data=None, size=(90, 90), page_number=0, page_size=None):
    """
    Альтернативный способ с использованием pdfrw
    """

    # Читаем основной документ
    template = PdfReader(fname=input_pdf, fdata=input_data)

    media_box = template.pages[page_number].MediaBox

    template_w = 0
    template_h = 0
    if media_box:
        template_w = int(float(media_box[2])) - int(float(media_box[0]))  # x1 - x0
        template_h = int(float(media_box[3])) - int(float(media_box[1]))  # y1 - y0


    if page_size:
        page_w = page_size[0]
        page_h = page_size[1]
    else:
        page_w = template_w
        page_h = template_h

    scale_x = template_w / page_w
    scale_y = template_h / page_h

    img_pos_x = int(scale_x * position[0])
    img_pos_y = int(scale_y * position[1])

    # Создаем PDF
    packet = io.BytesIO()
    ps = A4
    if page_h < page_w:
        ps = landscape(A4)
    # can = canvas.Canvas(packet, pagesize=ps)
    can = canvas.Canvas(packet, pagesize=(template_w, template_h))  # Используем реальные размеры
    can.drawImage(image,
                  img_pos_x, img_pos_y,
                  mask='auto',
                  width=size[0]*scale_x, height=size[1]*scale_y,
                  preserveAspectRatio=True)
    can.save()

    packet.seek(0)
    stamp = PdfReader(packet)


    # Добавляем печать на нужную страницу
    PageMerge(template.pages[page_number]).add(stamp.pages[0]).render()

    # Сохраняем результат
    if output_pdf:
        PdfWriter().write(output_pdf, template)
    else:
        file = io.BytesIO()
        PdfWriter().write(file, template)
        file.seek(0)
        return file.getvalue()


if __name__ == '__main__':
    os.makedirs('tmp', exist_ok=True)
    with open('/home/pvm/projects/bot-bills/tmp/Без имени 1.pdf', 'rb') as rdr:
        src = rdr.read()
    src = add_png_pdfrw(
        image='assets/images/sig_alla.png',
        input_data=src,
        size=(75, 80),
        position=(1240-80*2, 1754-75*2),
        page_size=(1240, 1754),
        page_number=0,
    )
    add_png_pdfrw(
        image='assets/images/pravila_pechat.png',
        input_data=src,
        output_pdf='tmp/example_stamp_sig.pdf',
        size=(75, 80),
        position=(1754-80*2, 1240-75*2),
        page_size=(1754, 1240),
        page_number=1,
    )
