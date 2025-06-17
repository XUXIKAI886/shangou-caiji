# 美团闪购产品采集工具

## 软件简介
本软件用于监控特定JSON数据文件，自动提取美团闪购产品信息，并整理为Excel表格和图片。

## 使用前准备
1. 下载并安装"Fiddler Classic"抓包软件
2. 打开Fiddler，点击菜单中的"Rules" > "Customize Rules..."
3. 在打开的脚本编辑器中，找到`OnBeforeResponse`函数
4. 在函数内部添加以下代码：
```
if(oSession.uriContains("https://wx-shangou.meituan.com/wxapp/v1/poi/")){
   oSession.utilDecodeResponse();
   oSession.SaveResponse("D:/ailun/shangou.txt",true);
   oSession.SaveResponseBody("D:/ailun/shangou.txt");
}
```
5. 保存并关闭脚本编辑器
6. 确保Fiddler处于抓包状态(Capturing状态)

## 快速开始
1. 在目标电脑上创建数据文件路径：`D:\ailun\shangou.txt`
2. 将整个软件文件夹复制到目标电脑
3. 打开Fiddler Classic并确保正在抓包
4. 双击`闪购采集工具.bat`启动程序

## 重要说明
- 软件为独立可执行程序，无需安装Python和依赖库
- 数据文件路径固定为：`D:\ailun\shangou.txt`
- 批处理文件必须与dist文件夹保持在同一目录层级
- 必须先运行Fiddler进行数据抓取，程序才能获取到数据源

## 输出文件
- Excel数据：`meituanshangou_products.xlsx`
- 产品图片：`meituanshangou_images_jpg/`
- 运行日志：`meituanshangou_monitor.log`

详细使用方法请查看`使用说明.txt`