<?php

namespace TGCode;

use pocketmine\command\Command;
use pocketmine\command\CommandSender;
use pocketmine\event\Listener;
use pocketmine\event\player\PlayerCommandPreprocessEvent;
use pocketmine\plugin\PluginBase;
use pocketmine\utils\Config;
use pocketmine\utils\TextFormat;

class TGCodePlugin extends PluginBase implements Listener {

    /** @var Config */
    private $codesConfig;

    public function onEnable() {
        if(!is_dir($this->getDataFolder())) {
            @mkdir($this->getDataFolder());
        }
        if(!is_dir($this->getDataFolder() . "codes/")) {
            @mkdir($this->getDataFolder() . "codes/");
        }
        $this->getServer()->getPluginManager()->registerEvents($this, $this);
        $this->codesConfig = new Config($this->getDataFolder() . "codes.yml", Config::YAML, []);
        $this->loadCodes();
        $this->getLogger()->info("\n§1~~~~~~~~~~~~~~~~~~~~~~~~~~
§aПлагин TGcode успешно запушен!
§4Версия плагина 1.0.0
§5Создатель плагина TGlink
§1~~~~~~~~~~~~~~~~~~~~~~~~~~");
    }


    public function onPlayerCommandPreprocess(PlayerCommandPreprocessEvent $event) {
        $message = $event->getMessage();
        $player = $event->getPlayer();
        $playerName = $player->getName();

        // Проверяем, начинается ли сообщение с команды "/tgcode"
        if (strtolower(substr($message, 0, 7)) === "/tgcode") {
            $this->handleTGCodeCommand($playerName, $event);
        } elseif (strtolower(substr($message, 0, 9)) === "/tgdelete") {
            $this->handleTGDeleteCommand($playerName, $event);
        }
    }

    public function handleTGCodeCommand(string $playerName, PlayerCommandPreprocessEvent $event): void {
        // Проверяем, существует ли уже код подтверждения для игрока
        if ($this->codesConfig->exists(strtolower($playerName))) {
            $event->getPlayer()->sendMessage("§7(§l§6H§l§fC§r§7) §l§cВы уже создали код подтверждения. Пожалуйста, удалите его командой /tgdelete, чтобы создать новый.");
            $event->setCancelled(true);
        } else {
            $code = $this->generateCode();
            $event->getPlayer()->sendMessage("§7(§l§6H§l§fC§r§7) §l§bПривязка §f§l• §7§lВаш §e§lкод §7§lпривязки §l§bTelegram:§l§f " . $code);
            $event->getPlayer()->sendMessage("§7(§l§6H§l§fC§r§7) §l§bПривязка §f§l• §f§lИнструкция §7§l по привязке §l§eаккаунта §l§7к §l§bTelegram §l§7боту! \n §l§f1. §l§7Найти в §l§bТелеграме §l§7бота §l§f@hlebcraft_bot \n §f§l2. §l§7Написать боту §f§l/link §l§7и следовать его инструкциям \n\n §8§l(§l§7P.S §l§fЕсли возникнут §l§cпроблемы §l§7вот §l§bТГ §l§7канал сервера: §l§f@hleb_craft \n §l§6В§l§fК §l§f@hleb_craft §l§8)");

            // Сохраняем код в файле
            $this->saveCode($playerName, $code);

            // Отменяем обработку команды "/tgcode" сервером
            $event->setCancelled(true);
        }
    }

    public function handleTGDeleteCommand(string $playerName, PlayerCommandPreprocessEvent $event): void {
        // Проверяем, существует ли код подтверждения для игрока
        if ($this->codesConfig->exists(strtolower($playerName))) {
            $this->codesConfig->remove(strtolower($playerName));
            $this->codesConfig->save();
            $event->getPlayer()->sendMessage("§7(§l§6H§l§fC§r§7) §7§lВаш код для §l§bTelegram §7§lбыл §l§aуспешно §l§7удален.");
        } else {
            $event->getPlayer()->sendMessage("§7(§l§6H§l§fC§r§7) §l§7У вас еще §l§cне создан §l§7код для §l§bTelegram.");
        }

        // Отменяем обработку команды "/tgdelete" сервером
        $event->setCancelled(true);
    }

    public function generateCode(): string {
        $characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
        $code = '';
        $length = strlen($characters);
        for ($i = 0; $i < 8; $i++) {
            $code .= $characters[mt_rand(0, $length - 1)];
        }
        return $code;
    }

    public function saveCode(string $playerName, string $code): void {
        $this->codesConfig->set(strtolower($playerName), ["code" => $code]);
        $this->codesConfig->save();
    }

    public function loadCodes(): void {
        $this->codes = $this->codesConfig->getAll();
    }

    public function onCommand(CommandSender $sender, Command $command, $label, array $args): bool {
        if ($command->getName() === "tgdelete") {
            if($sender instanceof \pocketmine\Player) {
                $playerName = $sender->getName();
                $this->handleTGDeleteCommand($playerName, null);
            } else {
                $sender->sendMessage(TextFormat::RED . "This command can only be used in-game.");
            }
        }
        return true;
    }
}
