<?php

namespace TGplaytime;

class PT extends \pocketmine\plugin\PluginBase implements \pocketmine\event\Listener {

    public $time;
    public $sec;
    public $lastSession;
    public $lastDate;

    public function __construct(){}


    public function onEnable(){
        if(!is_dir($this->getDataFolder()))
            @mkdir($this->getDataFolder());
        $this->getLogger()->info("\n§1~~~~~~~~~~~~~~~~~~~~~~~~~~
§aПлагин TGplaytime успешно запушен!
§4Версия плагина 1.0.0
§5Создатель плагина TGlink
§1~~~~~~~~~~~~~~~~~~~~~~~~~~");
        $this->time = new \pocketmine\utils\Config($this->getDataFolder() ."time.yml", \pocketmine\utils\Config::YAML);
        $this->lastSession = new \pocketmine\utils\Config($this->getDataFolder() ."last_session.yml", \pocketmine\utils\Config::YAML);
        $this->lastDate = new \pocketmine\utils\Config($this->getDataFolder() ."last_date.yml", \pocketmine\utils\Config::YAML);
        
        $this->getServer()->getScheduler()->scheduleRepeatingTask(new \pocketmine\scheduler\CallbackTask(array($this, "updateTimer")),  20 * 1);
        $this->getServer()->getPluginManager()->registerEvents($this, $this);
    }

    public function onPreJoin(\pocketmine\event\player\PlayerPreLoginEvent $e){
        if(!$this->time->exists(strtolower($e->getPlayer()->getName()))){
            $this->time->set(strtolower($e->getPlayer()->getName()), ["hour" => 0, "minute" => 0, "second" => 0]);
            $this->time->save();
        }
    }

    public function onJoin(\pocketmine\event\player\PlayerJoinEvent $e){
        $name = strtolower($e->getPlayer()->getName());
        $time = time();
        $this->lastSession->set($name . "_joined", time()); // Сохраняем время входа на сервер
        $this->lastSession->save();
    }

    public function onQuit(\pocketmine\event\player\PlayerQuitEvent $e){
        $name = strtolower($e->getPlayer()->getName());
        $joined = $this->lastSession->get($name . "_joined");
        if($joined !== false){
            $time = time() - $joined; // Вычисляем время пребывания на сервере в секундах
            $minutes = floor($time / 60); // Получаем количество прошедших минут
            $seconds = $time % 60; // Получаем количество прошедших секунд
            $this->lastSession->set($name, [
                "minutes" => $minutes,
                "seconds" => $seconds
            ]);
            $this->lastSession->remove($name . "_joined");
            $this->lastSession->save();
            
            // Записываем дату последнего выхода в файл
            $this->lastDate->set($name, [
                "date" => date("d.m.Y:H:i", time())
            ]);
            $this->lastDate->save();
        }
    }

    public function onCommand(\pocketmine\command\CommandSender $p, \pocketmine\command\Command $c, $label, array $args){
        if($c == "ptime"){
            $p->sendMessage("§l§6H§l§fC §l§8| §7§lВы наиграли за все время:\n§6". $this->time->get(strtolower($p->getName()))["hour"] ." §l§eЧасов, §6". $this->time->get(strtolower($p->getName()))["minute"] ." §l§eМинут");
        }
    }

    public function updateTimer(){
        foreach($this->getServer()->getOnlinePlayers() as $p){
            $name = strtolower($p->getName());
            $s = $this->time->get($name)["second"];
            $ss = $s + 1;
            $mmm = $this->time->get($name)["minute"];
            $hhh = $this->time->get($name)["hour"];
            if($ss == 60){
                $ss = 0;
                $mj = $this->time->get($name)["minute"];
                $mmm = $mj + 1;
            }
            if($mmm == 60){
                $mmm = 0;
                $hj = $this->time->get($name)["hour"];
                $hhh = $hj + 1;
            }
            $this->time->set($name, ["hour" => $hhh, "minute" => $mmm, "second" => $ss]);
            $this->time->save();
        }
    }
    /**
     * @Получение отигранных минут
     */
    public function getPlaytimeMinute($name){
        return $this->time->get(strtolower($name))["minute"];
    }
    /**
     * @Получение отигранных часов
     */
    public function getPlaytimeHour($name){
        return $this->time->get(strtolower($name))["hour"];
    }
    /**
     * @Получение отигранных секунд
     */
    public function getPlaytimeSecond($name){
        return $this->time->get(strtolower($name))["second"];
    }
    /**
     * @Получение отигранного времени @string
     */
    public function getAllTime($name){
        return $this->time->get(strtolower($name))["hour"] ."§fч§b ". $this->time->get(strtolower($name))["minute"] ."§fм§b ". $this->time->get(strtolower($name))["second"] ."§fс§b";
    }
}
?>
