## Веб сервис визуальной подписи PDF документов для интеграции в Nextcloud.

### Использовать:
* Загружать файл подписи с диска.
* Загружать предварительно подготовленные файлы с облачного хранилища.
* Нарисовать подпись мышью (на сенсорном экране стилусом, пальцем).

### Установка:

```shell
php occ app_api:app:register nc_ws_sign_app <deploy_daemon> --info-xml https://raw.githubusercontent.com/pvmezencev/nc_ws_sign_app/refs/heads/master/appinfo/info.xml
```

где deploy_daemon нужно заранее настроить, см. [инструкцию](https://docs.nextcloud.com/server/latest/admin_manual/exapps_management/AppAPIAndExternalApps.html#setup-deploy-daemon) 