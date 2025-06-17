# 美团闪购产品采集工具

## 软件简介
本软件用于监控特定JSON数据文件，自动提取美团闪购产品信息，并整理为Excel表格和图片。

## 快速开始
1. 在目标电脑上创建数据文件路径：`D:\ailun\shangou.txt`
2. 将整个软件文件夹复制到目标电脑
3. 双击`闪购采集工具.bat`启动程序

## 重要说明
- 软件为独立可执行程序，无需安装Python和依赖库
- 数据文件路径固定为：`D:\ailun\shangou.txt`
- 批处理文件必须与dist文件夹保持在同一目录层级

## 输出文件
- Excel数据：`meituanshangou_products.xlsx`
- 产品图片：`meituanshangou_images_jpg/`
- 运行日志：`meituanshangou_monitor.log`

详细使用方法请查看`使用说明.txt`