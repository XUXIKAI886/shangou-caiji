@echo off
chcp 65001 > nul
echo 正在启动美团闪购产品信息监控程序...
echo 请确保已安装所有依赖库(requirements.txt)
echo.
python simplified_meituanshangou_monitor.py
pause 