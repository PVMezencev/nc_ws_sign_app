import base64
import io
import json
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from nc_py_api import NextcloudApp
from nc_py_api.ex_app import LogLvl, set_handlers, persistent_storage
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from src.editor import add_png_pdfrw, convert_scanned_pdf_to_pdf

# Константы
APP_NAME = "nc_ws_sign_app"
DATA_DIR = Path(persistent_storage()) / "data"
TEMP_DIR = DATA_DIR / "temp"
ASSETS_DIR = Path(__file__).parent.parent / "assets"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Создаем необходимые директории
DATA_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)


# Очистка старых временных файлов (раз в день)
def cleanup_old_files():
    """Удаляет файлы старше 24 часов"""
    now = datetime.now()
    for item in TEMP_DIR.iterdir():
        if item.is_file():
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


# Middleware, который пропускает heartbeat
# class CustomAppAPIMiddleware(AppAPIAuthMiddleware):
#     async def dispatch(self, request: Request, call_next):
#         # Пропускаем heartbeat без проверки
#         if request.url.path == "/heartbeat":
#             return await call_next(request)
#         # Для всех остальных - стандартная проверка
#         return await super().dispatch(request, call_next)
#
#
# # Middleware для аутентификации
# APP.add_middleware(CustomAppAPIMiddleware)

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


# Эндпоинты
@APP.get("/")
async def index(request: Request, nc: NextcloudApp = Depends(NextcloudApp)):
    """Главная страница приложения"""
    user = nc.user

    # Генерируем ID сессии
    session_id = str(uuid.uuid4())

    return templates.TemplateResponse(
        request=request,
        name="editor.html",
        context={
            "user": user,
            "session_id": session_id,
            "version": "1.0.0"
        }
    )


@APP.get("/file/{file_id}")
async def edit_file(
        request: Request,
        file_id: int,
        nc: NextcloudApp = Depends(NextcloudApp)
):
    """Редактирование конкретного файла"""
    user = nc.user

    # Получаем информацию о файле из Nextcloud
    try:
        file_info = nc.files.by_id(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")

        # Скачиваем файл
        file_content = nc.files.download(file_info)

        # Сохраняем во временную директорию
        session_id = str(uuid.uuid4())
        session_dir = get_session_dir(user, session_id)
        pdf_path = session_dir / f"{session_id}.pdf"

        with open(pdf_path, "wb") as f:
            f.write(file_content)

        return templates.TemplateResponse(
            request=request,
            name="editor.html",
            context={
                "user": user,
                "session_id": session_id,
                "file_name": file_info.name,
                "file_id": file_id,
                "version": "1.0.0"
            }
        )
    except Exception as e:
        nc.log(LogLvl.ERROR, f"Error loading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@APP.get("/payload/{session_id}")
async def get_payload(
        session_id: str,
        nc: NextcloudApp = Depends(NextcloudApp)
):
    """Получение данных сессии"""
    user = nc.user
    session_dir = get_session_dir(user, session_id)
    payload_file = session_dir / f"payload.json"

    if not payload_file.exists():
        return JSONResponse(content={})

    with open(payload_file, 'r') as f:
        payload = json.load(f)

    # Добавляем подпись, если есть
    sign_file = session_dir / "signature.png"
    if sign_file.exists():
        with open(sign_file, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode()
            payload['sign'] = f'data:image/png;base64,{encoded}'

    return JSONResponse(content=payload)


@APP.post("/save_payload/{session_id}")
async def save_payload(
        session_id: str,
        payload: dict,
        nc: NextcloudApp = Depends(NextcloudApp)
):
    """Сохранение данных сессии"""
    user = nc.user
    session_dir = get_session_dir(user, session_id)
    payload_file = session_dir / "payload.json"

    with open(payload_file, 'w') as f:
        json.dump(payload, f)

    return JSONResponse(content={"message": "OK"})


@APP.post("/sign/{session_id}")
async def save_signature(
        session_id: str,
        result: Result,
        nc: NextcloudApp = Depends(NextcloudApp)
):
    """Сохранение подписи"""
    user = nc.user
    session_dir = get_session_dir(user, session_id)

    if result.signature_new:
        sign_file = session_dir / "signature.png"
        img_data = base64.b64decode(
            result.signature_new.replace('data:image/png;base64,', '')
        )
        with open(sign_file, 'wb') as f:
            f.write(img_data)

    return JSONResponse(content={'message': 'OK'})


@APP.post("/process/{session_id}")
async def process_document(
        session_id: str,
        result: Result,
        nc: NextcloudApp = Depends(NextcloudApp)
):
    """Обработка документа с подписями"""
    user = nc.user
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
        nc: NextcloudApp = Depends(NextcloudApp)
):
    """Сохранение результата в Nextcloud"""
    user = nc.user
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
        nc.log(LogLvl.ERROR, f"Error saving file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@APP.delete("/cleanup/{session_id}")
async def cleanup_session(
        session_id: str,
        nc: NextcloudApp = Depends(NextcloudApp)
):
    """Очистка временных файлов сессии"""
    user = nc.user
    session_dir = get_session_dir(user, session_id)

    if session_dir.exists():
        shutil.rmtree(session_dir)

    return JSONResponse(content={"message": "Cleaned up"})
