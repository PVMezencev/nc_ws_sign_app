<?php

declare(strict_types=1);

namespace OCA\WebServerSignDocApp\AppInfo;

use OCP\AppFramework\App;
use OCP\AppFramework\Bootstrap\IBootstrap;
use OCP\AppFramework\Bootstrap\IRegistrationContext;
use OCP\AppFramework\Bootstrap\IBootContext;
use OCP\IConfig;
use OCP\IURLGenerator;
use OCP\AppFramework\Http\TemplateResponse;

class Application extends App implements IBootstrap {
    public const APP_ID = 'ws_sign_app';

    public function __construct() {
        parent::__construct(self::APP_ID);
    }

    public function register(IRegistrationContext $context): void {
        // Регистрируем скрипты и стили для страниц приложения
        $context->registerInitialStateProvider(\OCA\WebServerSignDocApp\InitialState\AppState::class);
    }

    public function boot(IBootContext $context): void {
        $context->injectFn(function(IConfig $config, IURLGenerator $urlGenerator) {
            // Добавляем ссылку в меню Nextcloud
            \OCP\Util::addScript(self::APP_ID, 'main');
            \OCP\Util::addStyle(self::APP_ID, 'style');
            
            // Проверяем, запущено ли приложение
            $this->checkAppStatus();
        });
    }
    
    private function checkAppStatus(): void {
        // Здесь можно проверить, запущен ли Python сервис
        // и показать предупреждение, если нет
        $connection = @fsockopen('localhost', 9080, $errno, $errstr, 1);
        if (!$connection) {
            \OCP\Util::writeLog(
                self::APP_ID,
                'Python service is not running on port 9080. Please start it with: python3 src/main.py',
                \OCP\Util::WARN
            );
        } else {
            fclose($connection);
        }
    }
}