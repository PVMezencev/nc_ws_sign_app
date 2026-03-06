document.addEventListener('DOMContentLoaded', async function () {

    // Переменные для рисования подписи
    let isDrawing = false;
    let lastX = 0;
    let lastY = 0;
    let currentPageIndex = 0;
    let currentPageOrieentation = 'portrait';
    let pages = [];
    let signatureNew;
    let stampPravilaExists;
    let stampRpExists;
    let signatureCanvas;
    let signatureCtx;

    let w = 1240
    let h = 1754

    function dataURLtoFile(dataurl, filename) {
        let arr = dataurl.split(','),
            mime = arr[0].match(/:(.*?);/)[1],
            bstr = atob(arr[arr.length - 1]),
            n = bstr.length,
            u8arr = new Uint8Array(n);
        while (n--) {
            u8arr[n] = bstr.charCodeAt(n);
        }
        return new File([u8arr], filename, {type: mime});
    }

    // Инициализация canvas
    const canvas = new fabric.Canvas('pdf-canvas', {
        width: w,
        height: h,
    });

    function loadBackgroundImage(file, orieentation, canvas_width, canvas_height) {
        const reader = new FileReader();
        currentPageOrieentation = orieentation
        reader.onload = function (event) {

            // Создаем HTML изображение
            const img = new Image();
            img.onload = function () {

                // Создаем fabric.Image из HTMLImageElement
                const fabricImg = new fabric.Image(img);
                if (orieentation === 'portrait') {
                    canvas.setDimensions({width: canvas_width, height: canvas_height})
                    document.getElementById('canvas-container').style.width = canvas_width + 'px'
                    document.getElementById('canvas-container').style.height = canvas_height + 'px'
                } else {
                    canvas.setDimensions({width: canvas_height, height: canvas_width})
                    document.getElementById('canvas-container').style.width = canvas_height + 'px'
                    document.getElementById('canvas-container').style.height = canvas_width + 'px'
                }

                // Масштабируем под размер A4
                const scaleX = canvas.width / img.width;
                const scaleY = canvas.height / img.height;
                const scale = Math.min(scaleX, scaleY);

                fabricImg.set({
                    scaleX: scale,
                    scaleY: scale,
                    selectable: false,
                    evented: false,
                    name: 'background',
                    originX: 'left',
                    originY: 'top'
                });

                // Устанавливаем как фон
                canvas.setBackgroundImage(fabricImg, function () {
                    canvas.renderAll();
                });
            };

            img.onerror = function () {
            };

            img.src = event.target.result;
        };

        reader.onerror = function (error) {
        };

        reader.readAsDataURL(file);
    }

    function loadImageToCanvas(file, type) {
        const reader = new FileReader();

        reader.onload = function (event) {

            // Метод 1: Создаем через HTMLImageElement (самый надежный)
            const img = new Image();

            img.onload = function () {

                // Создаем fabric.Image
                const fabricImg = new fabric.Image(img);

                // Настройки
                const color = type === 'stamp_rp' || 'stamp_pravila' ? 'red' : 'blue';
                const maxSize = type === 'stamp_rp' || 'stamp_pravila' ? 150 : 200;

                // Автоматическое масштабирование
                let scale = 1;
                if (img.width > maxSize) {
                    scale = maxSize / img.width;
                }

                fabricImg.set({
                    left: 100,
                    top: 100,
                    scaleX: scale,
                    scaleY: scale,
                    cornerStyle: 'circle',
                    transparentCorners: false,
                    cornerColor: color,
                    cornerSize: 12,
                    borderColor: color,
                    name: type,
                    hasControls: true,
                    hasBorders: true
                });

                // Добавляем на canvas
                canvas.add(fabricImg);
                canvas.setActiveObject(fabricImg);
                canvas.renderAll();
            };

            img.onerror = function (err) {
                console.error('Image error:', err);

                // Пробуем альтернативный метод
                tryAlternativeMethod(event.target.result, type);
            };

            img.src = event.target.result;
        };

        reader.onerror = function (error) {
        };

        reader.readAsDataURL(file);
    }

    // Альтернативный метод на случай ошибок
    function tryAlternativeMethod(dataUrl, type) {

        // Пробуем fabric.Image.fromURL с промисом
        fabric.Image.fromURL(dataUrl)
            .then(function (img) {

                const color = type === 'stamp_rp' || 'stamp_pravila' ? 'red' : 'blue';
                const maxSize = type === 'stamp_rp' || 'stamp_pravila' ? 150 : 200;

                let scale = 1;
                if (img.width > maxSize) {
                    scale = maxSize / img.width;
                }

                img.set({
                    left: 150,
                    top: 150,
                    scaleX: scale,
                    scaleY: scale,
                    cornerStyle: 'circle',
                    transparentCorners: false,
                    cornerColor: color,
                    cornerSize: 12,
                    borderColor: color,
                    name: type
                });

                canvas.add(img);
                canvas.setActiveObject(img);
                canvas.renderAll();
            })
            .catch(function (error) {
                // Создаем временный объект вместо изображения
                createFallbackObject(type);
            });
    }

    // Создаем временный объект если изображение не загружается
    function createFallbackObject(type) {
        const color = type === 'stamp_rp' || 'stamp_pravila' ? 'red' : 'blue';
        const text = type === 'stamp_rp' || 'stamp_pravila' ? 'ПЕЧАТЬ' : 'ПОДПИСЬ';

        const rect = new fabric.Rect({
            width: 150,
            height: type === 'stamp_rp' || 'stamp_pravila' ? 150 : 80,
            fill: 'transparent',
            stroke: color,
            strokeWidth: 2,
            left: 100,
            top: 100,
            name: type
        });

        const textObj = new fabric.Text(text, {
            fontSize: 16,
            fill: color,
            left: 100,
            top: type === 'stamp_rp' || 'stamp_pravila' ? 100 : 110,
            name: type
        });

        const group = new fabric.Group([rect, textObj], {
            left: 100,
            top: 100,
            cornerStyle: 'circle',
            transparentCorners: false,
            cornerColor: color,
            cornerSize: 12,
            name: type
        });

        canvas.add(group);
        canvas.setActiveObject(group);
        canvas.renderAll();
    }

    // Получение координат и размеров
    function getPositions() {
        const objects = canvas.getObjects();
        const positions = [];
        objects.forEach(obj => {
            if (obj.name === 'stamp_rp' || obj.name === 'stamp_pravila' || obj.name === 'sign') {
                const scaledWidth = Math.round(obj.width * obj.scaleX);
                const scaledHeight = Math.round(obj.height * obj.scaleY);

                console.log(obj)

                let top = canvas.height - Math.round(obj.top) - scaledHeight
                let left = Math.round(obj.left)

                positions.push({
                    type: obj.name,
                    left: left,
                    top: top,
                    width: scaledWidth,
                    height: scaledHeight,
                    scaleX: Math.round(obj.scaleX * 100) / 100,
                    scaleY: Math.round(obj.scaleY * 100) / 100,
                    angle: Math.round(obj.angle)
                });
            }
        });

        const payload = {}
        payload.page = currentPageIndex
        payload.positions = positions
        payload.signature_new = signatureNew
        payload.page_size = {
            w: canvas.width,
            h: canvas.height,
        }

        return payload;
    }

    // Очистка всего canvas
    function clearAll() {
        canvas.clear();
        canvas.backgroundColor = '#f0f0f0';
        canvas.renderAll();
        document.getElementById('coordinates').textContent = 'Все объекты удалены';

        // Закрываем модальное окно подписи если открыто
        closeSignatureModal();
    }

    // Удаление выделенного объекта
    function removeSelected() {
        const activeObject = canvas.getActiveObject();
        if (activeObject) {
            canvas.remove(activeObject);
            canvas.renderAll();
            document.getElementById('coordinates').textContent = 'Выделенный объект удален';
        } else {
            alert('Выделите объект для удаления');
        }
    }

    // Функция начала рисования подписи
    function startDrawingSignature(event) {
        createSignatureModal();
    }

    // Создание модального окна для рисования
    function createSignatureModal() {
        // Создаем модальное окно
        const modal = document.getElementById('signature-modal');
        modal.style.display = 'flex';

        // Инициализируем canvas для подписи
        initializeSignatureCanvas();
    }

    // Обновите также инициализацию canvas для подписи, чтобы установить правильные размеры:
    function initializeSignatureCanvas() {
        signatureCanvas = document.getElementById('signature-canvas');
        signatureCtx = signatureCanvas.getContext('2d');

        // Устанавливаем правильные размеры canvas
        const container = signatureCanvas.parentElement;
        signatureCanvas.width = container.clientWidth;
        signatureCanvas.height = 200;

        // Настройки контекста для имитации шариковой ручки
        signatureCtx.strokeStyle = '#1e40af'; // Темно-синий цвет
        signatureCtx.lineWidth = 2;
        signatureCtx.lineCap = 'round';
        signatureCtx.lineJoin = 'round';
        signatureCtx.globalCompositeOperation = 'source-over';

        // Очищаем canvas
        clearSignature();

        // Добавляем обработчики событий
        signatureCanvas.addEventListener('mousedown', startSignatureDraw);
        signatureCanvas.addEventListener('mousemove', drawSignature);
        signatureCanvas.addEventListener('mouseup', stopSignatureDraw);
        signatureCanvas.addEventListener('mouseout', stopSignatureDraw);

        // Для сенсорных устройств
        signatureCanvas.addEventListener('touchstart', handleTouchStart);
        signatureCanvas.addEventListener('touchmove', handleTouchMove);
        signatureCanvas.addEventListener('touchend', stopSignatureDraw);
    }

    // Обработчики для мыши
    function startSignatureDraw(e) {
        isDrawing = true;
        const rect = signatureCanvas.getBoundingClientRect();
        const scaleX = signatureCanvas.width / rect.width;
        const scaleY = signatureCanvas.height / rect.height;

        lastX = (e.clientX - rect.left) * scaleX;
        lastY = (e.clientY - rect.top) * scaleY;

        // Начинаем путь
        signatureCtx.beginPath();
        signatureCtx.moveTo(lastX, lastY);
    }

    function drawSignature(e) {
        if (!isDrawing) return;

        const rect = signatureCanvas.getBoundingClientRect();
        const scaleX = signatureCanvas.width / rect.width;
        const scaleY = signatureCanvas.height / rect.height;

        const currentX = (e.clientX - rect.left) * scaleX;
        const currentY = (e.clientY - rect.top) * scaleY;

        // Рисуем линию с эффектом шариковой ручки
        signatureCtx.lineTo(currentX, currentY);
        signatureCtx.stroke();

        // Добавляем небольшую вариацию толщины для естественности
        signatureCtx.lineWidth = 2 + Math.random() * 0.5;

        lastX = currentX;
        lastY = currentY;
    }

    function stopSignatureDraw() {
        isDrawing = false;
        signatureCtx.beginPath(); // Завершаем текущий путь
    }

    // Обработчики для touch событий
    function handleTouchStart(e) {
        e.preventDefault();
        const rect = signatureCanvas.getBoundingClientRect();
        const scaleX = signatureCanvas.width / rect.width;
        const scaleY = signatureCanvas.height / rect.height;

        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousedown', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        signatureCanvas.dispatchEvent(mouseEvent);
    }

    function handleTouchMove(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousemove', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        signatureCanvas.dispatchEvent(mouseEvent);
    }

    // Очистка поля для подписи
    function clearSignature() {
        signatureCtx.clearRect(0, 0, signatureCanvas.width, signatureCanvas.height);
        signatureCtx.fillStyle = 'transparent';
        signatureCtx.fillRect(0, 0, signatureCanvas.width, signatureCanvas.height);
    }

    // Сохранение подписи
    function saveSignature() {
        // Проверяем, есть ли рисунок
        const imageData = signatureCtx.getImageData(0, 0, signatureCanvas.width, signatureCanvas.height);
        let isEmpty = true;

        for (let i = 3; i < imageData.data.length; i += 4) {
            if (imageData.data[i] > 0) {
                isEmpty = false;
                break;
            }
        }

        if (isEmpty) {
            alert('Пожалуйста, нарисуйте подпись перед сохранением');
            return;
        }

        // Создаем временный canvas для обработки
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        tempCanvas.width = signatureCanvas.width;
        tempCanvas.height = signatureCanvas.height;

        // Заливаем прозрачным фоном
        tempCtx.clearRect(0, 0, tempCanvas.width, tempCanvas.height);

        // Копируем только синие линии (имитация ручки)
        const imageDataOriginal = signatureCtx.getImageData(0, 0, signatureCanvas.width, signatureCanvas.height);
        const newImageData = tempCtx.createImageData(signatureCanvas.width, signatureCanvas.height);

        for (let i = 0; i < imageDataOriginal.data.length; i += 4) {
            const r = imageDataOriginal.data[i];
            const g = imageDataOriginal.data[i + 1];
            const b = imageDataOriginal.data[i + 2];
            const a = imageDataOriginal.data[i + 3];

            // Сохраняем только синие пиксели (подпись)
            if (b > 100 && r < 100 && g < 150 && a > 10) {
                newImageData.data[i] = 30;     // R
                newImageData.data[i + 1] = 64; // G
                newImageData.data[i + 2] = 175; // B (синий)
                newImageData.data[i + 3] = a;  // Alpha
            } else {
                // Прозрачный фон
                newImageData.data[i + 3] = 0;
            }
        }

        tempCtx.putImageData(newImageData, 0, 0);

        // Получаем base64 PNG с прозрачным фоном
        const signatureDataURL = tempCanvas.toDataURL('image/png');

        // Добавляем на основной canvas
        addSignatureToMainCanvas(signatureDataURL);

        // Закрываем модальное окно
        closeSignatureModal();
    }

    // Добавление нарисованной подписи на основной canvas
    function addSignatureToMainCanvas(dataURL) {
        fabric.Image.fromURL(dataURL, function (img) {
            const maxWidth = 200;
            let scale = 1;

            if (img.width > maxWidth) {
                scale = maxWidth / img.width;
            }

            img.set({
                left: 100,
                top: 100,
                scaleX: scale,
                scaleY: scale,
                cornerStyle: 'circle',
                transparentCorners: false,
                cornerColor: 'blue',
                cornerSize: 12,
                borderColor: 'blue',
                name: 'sign'
            });

            canvas.add(img);
            canvas.setActiveObject(img);
            canvas.renderAll();

            // Также можно получить base64 для сохранения
            signatureNew = dataURL

            saveNewSign({signature_new: signatureNew})

            // Или получить как ArrayBuffer
            getSignatureAsArrayBuffer(dataURL);
        });
    }

    // Получение подписи как ArrayBuffer
    function getSignatureAsArrayBuffer(dataURL) {
        // Убираем префикс data URL
        const base64 = dataURL.split(',')[1];

        // Декодируем base64 в бинарные данные
        const binaryString = atob(base64);
        const bytes = new Uint8Array(binaryString.length);

        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        return bytes;
    }

    // Закрытие модального окна
    function closeSignatureModal() {
        const modal = document.querySelector('.signature-modal');
        if (modal) {
            modal.style.display = 'none';
        }
        isDrawing = false;
    }

    // Переключение на страницу
    function switchToPage(pageIndex) {
        if (pageIndex < 0 || pageIndex >= pages.length) return;

        // Переключаемся на новую страницу
        currentPageIndex = pageIndex;

        let f = dataURLtoFile(pages[currentPageIndex].data, `page_${currentPageIndex}.png`)
        loadBackgroundImage(f, pages[currentPageIndex].orientation, w, h)
        document.getElementById('page-info').innerText = `Страница ${currentPageIndex + 1}`
    }

    // Навигация по страницам
    function nextPage() {
        if (currentPageIndex < pages.length - 1) {
            switchToPage(currentPageIndex + 1);
        }
    }

    function prevPage() {
        if (currentPageIndex > 0) {
            switchToPage(currentPageIndex - 1);
        }
    }

    function convertToBase64(file, onSuccess) {
        const reader = new FileReader();
        reader.onload = () => onSuccess(reader.result);
        reader.readAsDataURL(file);
    }

    async function downloadFile(data, chat_id, session_id, filename = 'document.pdf') {
        try {
            const response = await fetch(`/exapps/nc_ws_sign_app/document-result?session_id=${session_id}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const blob = await response.blob();
            const blobUrl = window.URL.createObjectURL(blob);

            const link = document.createElement('a');
            link.href = blobUrl;

            // Получаем имя файла из заголовка Content-Disposition
            const contentDisposition = response.headers.get('Content-Disposition');

            if (contentDisposition) {
                // Разбираем заголовок Content-Disposition
                const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);

                if (filenameMatch && filenameMatch[1]) {
                    filename = filenameMatch[1].replace(/['"]/g, '');

                    // Декодируем URL-encoded имена (если нужно)
                    filename = decodeURIComponent(filename);
                }
            }

            link.download = filename;
            link.style.display = 'none';

            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            // Очистка
            window.URL.revokeObjectURL(blobUrl);

        } catch (error) {
            console.error('Download error:', error);
            alert('Ошибка при скачивании файла');
        }
    }

    async function saveNewSign(data) {
        try {
            const response = await fetch(`/exapps/nc_ws_sign_app/sign`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

        } catch (error) {
            console.error('Download error:', error);
            alert('Ошибка при скачивании файла');
        }
    }

    // Получаем данные и создаем кнопки
    async function loadAndRenderButtons() {
        try {
            // Делаем запрос
            const response = await fetch('/exapps/nc_ws_sign_app/preform_nextcloud');
            const data = await response.json();

            // Находим контейнер для кнопок
            const container = document.getElementById('buttons-container');

            // Очищаем контейнер
            container.innerHTML = '';

            // Создаем кнопки для каждого preform
            data.preforms.forEach(item => {
                // Создаем кнопку
                const button = document.createElement('button');
                button.textContent = item.name;
                button.className = 'preform-button'; // опционально, для стилизации

                // Добавляем обработчик клика
                button.addEventListener('click', async () => await handleButtonClick(item.b64content, item.name));

                // Добавляем кнопку в контейнер
                container.appendChild(button);
            });

        } catch (error) {
            console.error('Ошибка при загрузке данных:', error);
        }
    }

// Функция-обработчик клика
    async function handleButtonClick(b64content, name) {
        signatureExists = b64content
        let f = dataURLtoFile(b64content, 'sign.png')
        loadImageToCanvas(f, 'sign');
        await saveNewSign({signature_new: b64content});
    }

    document.getElementById('clear-signature').onclick = function () {
        clearSignature()
    }

    document.getElementById('save-signature').onclick = function () {
        saveSignature()
    }

    document.getElementById('close-signature-modal').onclick = function () {
        closeSignatureModal()
    }

    document.getElementById('start-signature-canvas').onclick = function () {
        startDrawingSignature()
    }

    document.getElementById('get-positions').onclick = function () {
        let result = getPositions()
        downloadFile(result, chat_id, session_id)
    }
    document.getElementById('prev-page').onclick = function () {
        prevPage()
    }
    document.getElementById('next-page').onclick = function () {
        nextPage()
    }

    let signExistFileBtn = document.getElementById('sign-exist-file')
    if (signExistFileBtn) {
        signExistFileBtn.onclick = function () {
            let f = dataURLtoFile(signatureExists, 'sign.png')
            loadImageToCanvas(f, 'sign');
        }
    }

    let preformSyncBtn = document.getElementById('preform-sync')
    if (preformSyncBtn) {
        preformSyncBtn.onclick = async function () {
            await loadAndRenderButtons()
        }
    }

    let preformUploadBtn = document.getElementById('preform-upload')
    if (preformUploadBtn) {
        preformUploadBtn.onclick = function () {
            document.getElementById('sign-upload').click();
        }

        document.getElementById('sign-upload').addEventListener('change', async function (e) {
            const file = e.target.files[0];
            if (!file) return;

            // Проверка на PDF
            if (!file.name.toLowerCase().endsWith('.png')) {
                alert('Пожалуйста, выберите PDF файл');
                return;
            }

            convertToBase64(file, (base64) => {
                addSignatureToMainCanvas(base64);
                saveNewSign({signature_new: signatureNew})
            })

            // Очищаем input
            e.target.value = '';
        });
    }

    document.getElementById('zoom_plus').onclick = function () {
        let cw = canvas.width;
        let ch = canvas.height;
        w = cw * 1.1
        h = ch * 1.1
        canvas.backgroundImage.scaleToWidth(w);
        canvas.backgroundImage.scaleToHeight(h);
        canvas.setDimensions({width: w, height: h})
        canvas.renderAll();
        document.getElementById('canvas-container').style.width = w + 'px'
        document.getElementById('canvas-container').style.height = h + 'px'
    }
    document.getElementById('zoom_minus').onclick = function () {
        let cw = canvas.width;
        let ch = canvas.height;
        w = cw * 0.9
        h = ch * 0.9
        canvas.backgroundImage.scaleToWidth(w);
        canvas.backgroundImage.scaleToHeight(h);
        canvas.setDimensions({width: w, height: h})
        canvas.renderAll();
        document.getElementById('canvas-container').style.width = w + 'px'
        document.getElementById('canvas-container').style.height = h + 'px'
    }

    // Простая загрузка файла
    document.getElementById('upload-button').addEventListener('click', function () {
        document.getElementById('file-upload').click();
    });

    document.getElementById('file-upload').addEventListener('change', async function (e) {
        const file = e.target.files[0];
        if (!file) return;

        // Проверка на PDF
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            alert('Пожалуйста, выберите PDF файл');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/exapps/nc_ws_sign_app/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Ошибка загрузки');

            const data = await response.json();
            pages = data.payload || []
            if (pages.length > 0) {
                let f = dataURLtoFile(pages[0].data, 'page_0.png')
                loadBackgroundImage(f, pages[0].orientation, w, h)
            }
            signatureExists = data.sign
            session_id = data.session_id || ''
        } catch (error) {
            console.error('Upload error:', error);
            alert('Ошибка при загрузке файла');
        }

        // Очищаем input
        e.target.value = '';
    });

    let response = await fetch(`/exapps/nc_ws_sign_app/payload/?session_id=${session_id}`);

    if (response.ok) { // если HTTP-статус в диапазоне 200-299
        // получаем тело ответа (см. про этот метод ниже)
        let json = await response.json();
        pages = json.payload || []
        if (pages.length > 0) {
            let f = dataURLtoFile(pages[0].data, 'page_0.png')
            loadBackgroundImage(f, pages[0].orientation, w, h)
        }
        signatureExists = json.sign
    } else {
        alert("Ошибка HTTP: " + response.status);
    }

    await loadAndRenderButtons()

});