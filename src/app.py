import base64
import io
import json
import os
import shutil
import typing
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from nc_py_api import NextcloudApp, AsyncNextcloudApp
from nc_py_api.ex_app import LogLvl, set_handlers, persistent_storage, anc_app, AppAPIAuthMiddleware
from pandas.io.sas.sas_constants import magic
from pydantic import BaseModel
from starlette.responses import StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pdf2image import convert_from_bytes

from src.editor import add_png_pdfrw, convert_scanned_pdf_to_pdf, create_image_reader

# Константы
APP_NAME = "nc_ws_sign_app"
DATA_DIR = Path(persistent_storage()) / "data"
TEMP_DIR = DATA_DIR / "temp"
ASSETS_DIR = Path(__file__).parent.parent / "assets"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Создаем необходимые директории
DATA_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

SIGN_FILE = 'new_sign.png'


# Очистка старых временных файлов (раз в день)
def cleanup_old_files():
    """Удаляет файлы старше 24 часов"""
    now = datetime.now()
    for item in TEMP_DIR.iterdir():
        if item.is_file():
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            if now - mtime > timedelta(hours=24):
                item.unlink()
    for item in DATA_DIR.iterdir():
        if item.is_file():
            if item.suffix not in ['.pdf', '.json']:
                continue
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            if now - mtime > timedelta(hours=24):
                item.unlink()


# Функция, которая вызывается при включении/выключении приложения
def enabled_handler(enabled: bool, nc: NextcloudApp) -> str:
    if enabled:
        nc.log(LogLvl.WARNING, f"Приложение {APP_NAME} включено!")
        cleanup_old_files()
    else:
        nc.log(LogLvl.WARNING, f"Приложение {APP_NAME} выключено.")
    return ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Регистрация обработчиков
    set_handlers(app, enabled_handler)

    # Очистка при старте
    cleanup_old_files()

    yield

    # Очистка при завершении
    cleanup_old_files()


# Создание приложения FastAPI
APP = FastAPI(
    title="PDF Signer",
    version="1.0.0",
    lifespan=lifespan
)

APP.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cloud.zaosmm.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware, который пропускает heartbeat
class CustomAppAPIMiddleware(AppAPIAuthMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Пропускаем heartbeat без проверки
        if request.url.path == "/heartbeat":
            return await call_next(request)
        # Для всех остальных - стандартная проверка
        return await super().dispatch(request, call_next)


# Middleware для аутентификации
APP.add_middleware(CustomAppAPIMiddleware)

# Монтируем статические файлы
APP.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# Шаблоны
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# Модели данных
class Result(BaseModel):
    page: int | None = None
    signature_new: str | None = None
    positions: list | None = None
    page_size: dict | None = None


class SignRequest(BaseModel):
    file_id: int
    session_id: str
    positions: list
    page: int = 0
    page_size: dict = None


# Вспомогательные функции
def get_user_dir(user_id: str) -> Path:
    """Возвращает путь к директории пользователя"""
    user_dir = DATA_DIR / user_id
    user_dir.mkdir(exist_ok=True)
    return user_dir


def get_session_dir(user_id: str, session_id: str) -> Path:
    """Возвращает путь к директории сессии"""
    session_dir = get_user_dir(user_id) / session_id
    session_dir.mkdir(exist_ok=True)
    return session_dir


@APP.post("/upload")
async def upload_file(
        request: Request,
        nc: typing.Annotated[AsyncNextcloudApp, Depends(anc_app)],
        file: UploadFile = File(...),
):
    """Загрузка файла с фронтенда для редактирования"""
    user = await nc.user

    # Проверяем размер файла (например, максимум 50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    # Проверяем, что это PDF
    # Способ 1: по расширению
    if not file.filename.lower().endswith('.pdf'):
        # Способ 2: по MIME типу (более надежно)
        mime_type = magic.from_buffer(contents, mime=True)
        if mime_type != 'application/pdf':
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Генерируем ID сессии
    session_id = str(uuid.uuid4())
    session_dir = get_session_dir(user, session_id)
    pdf_path = session_dir / f"{session_id}.pdf"

    images = convert_from_bytes(contents)
    payload = []
    for num in range(len(images)):
        img = images[num]

        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        encoded_data = base64.b64encode(img_byte_arr)
        item = {
            'page': num,
            'size': img.size,
            'data': 'data:image/png;base64,' + encoded_data.decode(),
        }
        if img.size[0] < img.size[1]:
            item['orientation'] = 'portrait'
        else:
            item['orientation'] = 'landscape'
        payload.append(item)
    if len(payload) == 0:
        raise HTTPException(status_code=400, detail="не удалось получить файл")

    payload_fp = os.path.join(session_dir, f'{session_id}.json')
    with open(payload_fp, 'w') as w:
        w.write(json.dumps({'payload': payload}, ensure_ascii=False))

    with open(pdf_path, 'wb') as w:
        w.write(contents)

    # Логируем успешную загрузку
    await nc.log(LogLvl.ERROR, f"File uploaded: {file.filename}, size: {len(contents)} bytes")

    user_dir = get_user_dir(user)
    sign_fp = Path(os.path.join(user_dir, SIGN_FILE))
    sign = ''
    if sign_fp.exists():
        with open(sign_fp, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode()
            sign = f'data:image/png;base64,{encoded}'

    return JSONResponse(content={'payload': payload, 'session_id': session_id, 'sign': sign})


@APP.get("/")
async def start_editor(request: Request,
                       nc: typing.Annotated[AsyncNextcloudApp, Depends(anc_app)],
                       session_id: str | None = None):
    user = await nc.user
    # Добавляем подпись, если есть
    has_sign = False
    user_dir = get_user_dir(user)
    sign_fp = Path(os.path.join(user_dir, SIGN_FILE))
    sign = ''
    if sign_fp.exists():
        has_sign = True
        with open(sign_fp, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode()
            sign = f'data:image/png;base64,{encoded}'
    if session_id is None:
        session_id = str(uuid.uuid4())
        return templates.TemplateResponse(
            request=request,
            name="editor.html",
            context={
                "user": user,
                "chat_id": user,
                "session_id": session_id,
                'has_sign': has_sign,
                'sign': sign,
                "version": "1.0.0"
            }
        )

    return templates.TemplateResponse(
        request=request, name="editor.html",
        context={
            "session_id": session_id,
            "chat_id": f'{user}',
            "user": user,
            'has_sign': has_sign,
            'sign': sign,
            'version': '1.0.2'}
    )


@APP.get("/payload/")
async def get_payload(
        session_id: str,
        nc: typing.Annotated[AsyncNextcloudApp, Depends(anc_app)]
):
    """Получение данных сессии"""
    user = await nc.user
    session_dir = get_session_dir(user, session_id)
    payload_fp = Path(os.path.join(session_dir, f'{session_id}.json'))

    if not payload_fp.exists():
        return JSONResponse(content={})

    with open(payload_fp, 'r') as f:
        payload = json.load(f)

    # Добавляем подпись, если есть
    user_dir = get_user_dir(user)
    sign_fp = Path(os.path.join(user_dir, SIGN_FILE))
    if sign_fp.exists():
        with open(sign_fp, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode()
            payload['sign'] = f'data:image/png;base64,{encoded}'

    return JSONResponse(content=payload)


@APP.post("/save_payload/{session_id}")
async def save_payload(
        session_id: str,
        payload: dict,
        nc: typing.Annotated[AsyncNextcloudApp, Depends(anc_app)]
):
    """Сохранение данных сессии"""
    user = await nc.user
    session_dir = get_session_dir(user, session_id)
    payload_file = session_dir / "payload.json"

    with open(payload_file, 'w') as f:
        json.dump(payload, f)

    return JSONResponse(content={"message": "OK"})


@APP.post("/sign")
async def save_signature(
        result: Result,
        nc: typing.Annotated[AsyncNextcloudApp, Depends(anc_app)]
):
    """Сохранение подписи"""
    user = await nc.user
    user_dir = get_user_dir(user)

    if result.signature_new:
        sign_file = user_dir / SIGN_FILE
        img_data = base64.b64decode(
            result.signature_new.replace('data:image/png;base64,', '')
        )
        with open(sign_file, 'wb') as f:
            f.write(img_data)

    return JSONResponse(content={'message': 'OK'})


@APP.post("/document-result")
async def result(result: Result,
                 nc: typing.Annotated[AsyncNextcloudApp, Depends(anc_app)],
                 session_id: str | None = None):
    user = await nc.user
    res = result.model_dump()
    new_sign = res.get('signature_new')
    page = res.get('page')
    positions = res.get('positions')
    page_size = res.get('page_size')
    page_w = page_size.get('w')
    page_h = page_size.get('h')

    session_dir = get_session_dir(user, session_id)
    user_dir = get_user_dir(user)
    pdf_path = session_dir / f"{session_id}.pdf"
    sign_fp = os.path.join(user_dir, SIGN_FILE)
    if new_sign and new_sign != '':
        with open(sign_fp, 'wb') as wr:
            im_bytes = base64.b64decode(new_sign.replace('data:image/png;base64,', ''))
            wr.write(im_bytes)

    with open(pdf_path, 'rb') as rdr:
        signet = rdr.read()
    signet = convert_scanned_pdf_to_pdf(signet)
    for pos in positions:
        top = pos.get('top')
        left = pos.get('left')
        width = pos.get('width')
        height = pos.get('height')
        print(pos)
        if pos.get('type') == 'sign':
            if new_sign:
                im_bytes = base64.b64decode(new_sign.replace('data:image/png;base64,', ''))
                imgredr = create_image_reader(io.BytesIO(im_bytes))
                signet = add_png_pdfrw(
                    image=imgredr,
                    input_data=signet,
                    size=(width, height),
                    position=(left, top),
                    page_number=page,
                    page_size=(page_w, page_h)
                )
            else:
                sign_path = 'assets/images/sig_alla.png'
                if os.path.exists(sign_fp):
                    sign_path = sign_fp
                signet = add_png_pdfrw(
                    image=sign_path,
                    input_data=signet,
                    size=(width, height),
                    position=(left, top),
                    page_number=page,
                    page_size=(page_w, page_h),
                )
        elif pos.get('type') == 'stamp_pravila':
            signet = add_png_pdfrw(
                image='assets/images/pravila_pechat.png',
                input_data=signet,
                size=(width, height),
                position=(left, top),
                page_number=page,
                page_size=(page_w, page_h),
            )
        elif pos.get('type') == 'stamp_rp':
            signet = add_png_pdfrw(
                image='assets/images/ruspriority_pechat.png',
                input_data=signet,
                size=(width, height),
                position=(left, top),
                page_number=page,
                page_size=(page_w, page_h),
            )

    sig_stamp_name = 'r_sig_stamp.pdf'

    return StreamingResponse(
        io.BytesIO(signet),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={sig_stamp_name}"}
    )


@APP.post("/process/{session_id}")
async def process_document(
        session_id: str,
        result: Result,
        nc: typing.Annotated[AsyncNextcloudApp, Depends(anc_app)]
):
    """Обработка документа с подписями"""
    user = await nc.user
    session_dir = get_session_dir(user, session_id)

    # Сохраняем подпись, если есть
    if result.signature_new:
        sign_file = session_dir / "signature.png"
        img_data = base64.b64decode(
            result.signature_new.replace('data:image/png;base64,', '')
        )
        with open(sign_file, 'wb') as f:
            f.write(img_data)

    # Загружаем PDF
    pdf_file = session_dir / f"{session_id}.pdf"
    if not pdf_file.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")

    with open(pdf_file, 'rb') as f:
        pdf_data = f.read()

    # Конвертируем если нужно
    pdf_data = convert_scanned_pdf_to_pdf(pdf_data)

    # Применяем все подписи и печати
    for pos in result.positions or []:
        top = pos.get('top')
        left = pos.get('left')
        width = pos.get('width')
        height = pos.get('height')
        pos_type = pos.get('type')

        if pos_type == 'sign':
            # Используем подпись пользователя
            sign_file = session_dir / "signature.png"
            if sign_file.exists():
                image_source = sign_file
            else:
                raise HTTPException(status_code=400, detail="signature file not found")

            pdf_data = add_png_pdfrw(
                image=str(image_source),
                input_data=pdf_data,
                size=(width, height),
                position=(left, top),
                page_number=result.page or 0,
                page_size=(result.page_size.get('w'), result.page_size.get('h')) if result.page_size else None
            )
        else:
            raise HTTPException(status_code=400, detail="unknown operation")

    # Сохраняем результат
    output_file = session_dir / "result.pdf"
    with open(output_file, 'wb') as f:
        f.write(pdf_data)

    return StreamingResponse(
        io.BytesIO(pdf_data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=signed_document.pdf"
        }
    )


@APP.post("/save_to_nextcloud/{session_id}")
async def save_to_nextcloud(
        session_id: str,
        filename: str,
        nc: typing.Annotated[AsyncNextcloudApp, Depends(anc_app)]
):
    """Сохранение результата в Nextcloud"""
    user = await nc.user
    session_dir = get_session_dir(user, session_id)
    result_file = session_dir / "result.pdf"

    if not result_file.exists():
        raise HTTPException(status_code=404, detail="Result file not found")

    with open(result_file, 'rb') as f:
        file_content = f.read()

    # Сохраняем в домашнюю директорию пользователя
    try:
        # Получаем путь к папке Documents или создаем свою
        save_path = f"/Documents/{filename}"
        if not filename.endswith('.pdf'):
            save_path += '.pdf'

        uploaded = nc.files.upload(save_path, file_content)

        return JSONResponse(content={
            "message": "File saved successfully",
            "file_id": uploaded.file_id,
            "path": save_path
        })
    except Exception as e:
        await nc.log(LogLvl.ERROR, f"Error saving file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@APP.get("/preform_nextcloud")
async def preform_nextcloud(
        nc: typing.Annotated[AsyncNextcloudApp, Depends(anc_app)]
):
    """Сохранение результата в Nextcloud"""
    user = await nc.user

    # Сохраняем в домашнюю директорию пользователя
    try:
        # Получаем путь к папке Documents или создаем свою
        preforms_dir = f"/Подпись документов/заготовки"

        files = []
        preforms = await nc.files.listdir(preforms_dir)
        for node in preforms:
            if node.is_dir:
                pass
            else:
                content = await nc.files.download(node.user_path)
                files.append({
                    'name': node.name,
                    'b64content': f'data:image/png;base64,{base64.b64encode(content).decode()}'
                })

        return JSONResponse(content={
            "preforms": files
        })
    except Exception as e:
        await nc.log(LogLvl.ERROR, f"Error saving file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@APP.delete("/cleanup/{session_id}")
async def cleanup_session(
        session_id: str,
        nc: typing.Annotated[AsyncNextcloudApp, Depends(anc_app)]
):
    """Очистка временных файлов сессии"""
    user = await nc.user
    session_dir = get_session_dir(user, session_id)

    if session_dir.exists():
        shutil.rmtree(session_dir)

    return JSONResponse(content={"message": "Cleaned up"})
