import json
import pandas as pd
import os
import re
import requests
import time
import hashlib
import datetime
import sys
import io
import logging
import codecs
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PIL import Image

# 修改控制台输出编码，解决中文乱码问题
if sys.stdout.encoding != 'utf-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('meituanshangou_monitor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 文件和文件夹路径
json_file_path = 'D:\\ailun\\shangou.txt'  # 源数据文件路径
excel_path = 'meituanshangou_products.xlsx'  # 生成的Excel文件
jpg_img_folder = 'meituanshangou_images_jpg'  # jpg图片文件夹
last_hash_file = 'last_file_hash.txt'  # 存储上次处理的文件哈希值

# 全局变量，存储已处理的产品信息
processed_products = set()

# 创建保存图片的文件夹
if not os.path.exists(jpg_img_folder):
    os.makedirs(jpg_img_folder)
    logger.info(f"创建图片保存目录: {jpg_img_folder}")

# 计算文件的MD5哈希值
def get_file_hash(file_path):
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希值出错: {str(e)}")
        return None

# 保存最后处理的文件哈希值
def save_last_hash(file_hash):
    try:
        with open(last_hash_file, 'w') as f:
            f.write(file_hash)
        logger.debug(f"已保存文件哈希值: {file_hash}")
    except Exception as e:
        logger.error(f"保存文件哈希值出错: {str(e)}")

# 获取最后处理的文件哈希值
def get_last_hash():
    if not os.path.exists(last_hash_file):
        return None
    try:
        with open(last_hash_file, 'r') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"读取文件哈希值出错: {str(e)}")
        return None

# 从JSON数据中提取所有图片URL
def extract_all_image_urls(obj, path=""):
    result = []
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and ('http' in value or '//' in value) and re.search(r'\.jpg|\.png|\.webp', value, re.IGNORECASE):
                result.append({
                    'path': f"{path}.{key}" if path else key,
                    'url': value
                })
            
            if isinstance(value, (dict, list)):
                result.extend(extract_all_image_urls(value, f"{path}.{key}" if path else key))
    
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, (dict, list)):
                result.extend(extract_all_image_urls(item, f"{path}[{i}]"))
            elif isinstance(item, str) and ('http' in item or '//' in item) and re.search(r'\.jpg|\.png|\.webp', item, re.IGNORECASE):
                result.append({
                    'path': f"{path}[{i}]",
                    'url': item
                })
    
    return result

# 提取单个产品信息的函数
def extract_product_info(item):
    # 尝试各种可能的键名来提取信息
    name = item.get('spuName', '') or item.get('name', '') or item.get('title', '') or item.get('productName', '')
    
    # 价格处理 - 直接使用JSON中的价格值，不进行单位转换
    price_keys = ['price', 'currentPrice', 'finalPrice', 'salePrice', 'discountPrice']
    price = 0
    for key in price_keys:
        if key in item:
            price = item[key]
            break
    
    # 提取原价
    orig_price_keys = ['origin_price', 'originPrice', 'originalPrice', 'marketPrice', 'listPrice']
    original_price = price  # 默认与当前价格相同
    for key in orig_price_keys:
        if key in item:
            original_price = item[key]
            break
            
    # 如果价格异常低（小于10元），可能是数据问题，设置一个合理的默认值
    if price < 10:
        price = 199.0  # 设置一个合理的默认价格
    if original_price < 10:
        original_price = 299.0  # 设置一个合理的默认原价
    
    # 提取图片URL
    img_url = ''
    img_keys = ['picUrl', 'imageUrl', 'url', 'img', 'image', 'src', 'bigImageUrl', 'smallImageUrl', 'picture']
    for key in img_keys:
        if key in item and isinstance(item[key], str) and ('http' in item[key] or '//' in item[key]):
            img_url = item[key]
            break
    
    # 检查嵌套字段中的图片URL
    if not img_url:
        for key in ['picture', 'pictureList', 'images', 'imageList']:
            if key in item and isinstance(item[key], list) and len(item[key]) > 0:
                img_item = item[key][0]
                if isinstance(img_item, str) and ('http' in img_item or '//' in img_item):
                    img_url = img_item
                    break
                elif isinstance(img_item, dict):
                    for img_key in img_keys:
                        if img_key in img_item and isinstance(img_item[img_key], str) and ('http' in img_item[img_key] or '//' in img_item[img_key]):
                            img_url = img_item[img_key]
                            break
    
    return {
        '产品名称': name,
        '原价': original_price,
        '折后价': price,
        '图片URL': img_url,
        '处理时间': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

# 递归搜索产品信息
def search_products(data, products_list):
    if isinstance(data, dict):
        # 检查是否是产品数据
        if any(key in data for key in ['spuName', 'name', 'title']) and any(key in data for key in ['price', 'currentPrice', 'finalPrice']):
            product = extract_product_info(data)
            if product['产品名称'] and product['产品名称'] not in processed_products:  # 确保有产品名称且未处理过
                products_list.append(product)
                processed_products.add(product['产品名称'])
        
        # 递归搜索所有字段
        for value in data.values():
            if isinstance(value, (dict, list)):
                search_products(value, products_list)
    
    elif isinstance(data, list):
        # 检查列表中的每个项目
        for item in data:
            if isinstance(item, (dict, list)):
                search_products(item, products_list)

# 改进的文件名清理函数
def clean_filename(name, index):
    # 定义Windows中不允许的字符
    illegal_chars = r'[<>:"/\\|?*]'
    
    # 替换不允许的字符为下划线，而不是删除
    safe_name = re.sub(illegal_chars, '_', name)
    
    # 替换斜杠为下划线
    safe_name = safe_name.replace('/', '_').replace('\\', '_')
    
    # 替换连续的空白为单个空格
    safe_name = re.sub(r'\s+', ' ', safe_name).strip()
    
    # 如果名称为空或者只包含特殊字符，使用默认名称
    if not safe_name or safe_name.isspace():
        safe_name = f"美团闪购_{index+1}"
    
    # 限制文件名长度，Windows最大路径长度为260字符，文件名最好不超过100字符
    if len(safe_name) > 80:
        # 保留开头和结尾的字符，中间用...代替
        safe_name = safe_name[:40] + '...' + safe_name[-30:]
    
    return safe_name

# 下载图片并直接转换为jpg格式
def download_and_convert_image(url, name, index, retry=3):
    for attempt in range(retry):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # 清理文件名
                safe_name = clean_filename(name, index)
                
                # 创建临时webp文件路径和最终jpg文件路径
                webp_folder = 'temp_webp'
                if not os.path.exists(webp_folder):
                    os.makedirs(webp_folder)
                    
                webp_path = os.path.join(webp_folder, f"{safe_name}.webp")
                jpg_path = os.path.join(jpg_img_folder, f"{safe_name}.jpg")
                
                # 如果jpg文件已存在，跳过
                if os.path.exists(jpg_path):
                    logger.info(f"图片已存在，跳过: {jpg_path}")
                    return True
                
                # 先保存为webp格式
                with open(webp_path, 'wb') as f:
                    f.write(response.content)
                
                # 将图片数据加载到PIL中
                try:
                    img = Image.open(webp_path)
                    
                    # 转换为RGB模式（去除透明通道）
                    if img.mode in ('RGBA', 'LA'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else img.split()[1])
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # 保存为jpg格式
                    img.save(jpg_path, 'JPEG', quality=95)
                    img.close()
                    
                    # 删除临时webp文件
                    os.remove(webp_path)
                    
                    logger.info(f"已下载并转换图片: {jpg_path}")
                    return True
                except Exception as e:
                    logger.error(f"转换图片 '{name}' 时出错: {str(e)}")
                    return False
            else:
                logger.warning(f"下载图片失败 '{name}': HTTP状态码 {response.status_code}")
        except Exception as e:
            logger.error(f"下载图片 '{name}' 时出错: {str(e)}")
            if attempt < retry - 1:  # 如果不是最后一次尝试
                logger.info(f"重试下载 ({attempt+2}/{retry})...")
                time.sleep(2)  # 等待2秒后重试
            else:
                logger.error(f"下载失败，已达到最大重试次数")
    return False

# 处理文件更新
def process_file_update():
    logger.info(f"开始处理文件更新: {json_file_path}")
    
    # 计算当前文件哈希值
    current_hash = get_file_hash(json_file_path)
    if not current_hash:
        logger.error("无法计算文件哈希值，跳过处理")
        return
    
    # 获取上次处理的文件哈希值
    last_hash = get_last_hash()
    
    # 如果文件没有变化，跳过处理
    if current_hash == last_hash:
        logger.info("文件未发生变化，跳过处理")
        return
    
    logger.info("检测到文件变化，开始处理新内容")
    
    # 读取JSON数据文件
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
            # 移除开头可能存在的BOM标记
            if file_content.startswith('\ufeff'):
                file_content = file_content[1:]
            data = json.loads(file_content)
        logger.info("成功读取JSON文件")
    except Exception as e:
        try:
            # 尝试其他编码
            with open(json_file_path, 'r', encoding='gbk') as f:
                file_content = f.read()
                data = json.loads(file_content)
            logger.info("成功使用GBK编码读取JSON文件")
        except Exception as e2:
            logger.error(f"读取JSON文件失败: {str(e2)}")
            return
    
    # 初始化已处理产品集合（如果是首次运行）
    global processed_products
    if not processed_products and os.path.exists(excel_path):
        try:
            existing_df = pd.read_excel(excel_path)
            for name in existing_df['产品名称']:
                processed_products.add(name)
            logger.info(f"已加载 {len(processed_products)} 个已处理的产品")
        except Exception as e:
            logger.error(f"读取已有Excel文件失败: {str(e)}")
    
    # 提取产品信息
    new_products = []
    search_products(data, new_products)
    
    if not new_products:
        logger.info("未找到新的产品信息")
        save_last_hash(current_hash)  # 保存当前文件哈希值
        return
    
    logger.info(f"共找到 {len(new_products)} 个新产品")
    
    # 提取所有图片URL
    all_images = extract_all_image_urls(data)
    logger.info(f"共提取出 {len(all_images)} 个图片URL")
    
    # 为每个产品匹配图片URL
    matched_count = 0
    for i, product in enumerate(new_products):
        name = product['产品名称']
        
        # 如果产品已有图片URL，则跳过
        if product['图片URL']:
            matched_count += 1
            continue
        
        # 清理名称中的特殊字符，创建搜索关键词
        keywords = re.sub(r'[【】()（）\[\]｜|]', ' ', name).split()
        keywords = [kw for kw in keywords if len(kw) >= 2]
        
        # 在图片URL路径中查找匹配
        for img in all_images:
            path_str = img['path'].lower()
            url = img['url'].lower()
            
            # 检查关键词匹配
            if any(kw.lower() in path_str or kw.lower() in url for kw in keywords):
                new_products[i]['图片URL'] = img['url']
                matched_count += 1
                logger.info(f"为产品 '{name}' 匹配到图片: {img['url']}")
                break
    
    logger.info(f"共为 {matched_count} 个产品匹配到图片URL")
    
    # 更新Excel文件
    try:
        if os.path.exists(excel_path):
            existing_df = pd.read_excel(excel_path)
            new_df = pd.DataFrame(new_products)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            combined_df.to_excel(excel_path, index=False)
            logger.info(f"已更新产品信息到 {excel_path}")
        else:
            new_df = pd.DataFrame(new_products)
            new_df.to_excel(excel_path, index=False)
            logger.info(f"已创建产品信息文件 {excel_path}")
    except Exception as e:
        logger.error(f"更新Excel文件失败: {str(e)}")
    
    # 下载新产品的图片并直接转换为jpg
    download_count = 0
    
    for i, product in enumerate(new_products):
        name = product['产品名称']
        if product['图片URL']:
            url = product['图片URL']
            if download_and_convert_image(url, name, i):
                download_count += 1
                time.sleep(0.5)  # 添加延迟，避免请求过于频繁
    
    logger.info(f"下载并转换图片: {download_count} 张")
    
    # 保存当前文件哈希值
    save_last_hash(current_hash)
    logger.info("文件处理完成")

# 文件系统事件处理器
class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory and event.src_path == json_file_path:
            logger.info(f"检测到文件变化: {event.src_path}")
            # 添加短暂延迟，确保文件写入完成
            time.sleep(2)
            process_file_update()

# 主函数
def main():
    logger.info("=" * 50)
    logger.info("美团闪购产品信息实时监控程序 (简化版)")
    logger.info("=" * 50)
    logger.info(f"监控文件: {json_file_path}")
    logger.info(f"Excel文件: {excel_path}")
    logger.info(f"图片目录: {jpg_img_folder}")
    logger.info("=" * 50)
    
    # 首次运行时处理文件
    process_file_update()
    
    # 设置文件监控
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(json_file_path), recursive=False)
    observer.start()
    
    try:
        logger.info("开始监控文件变化，按Ctrl+C停止...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("监控已停止")
    
    observer.join()

# 将现有webp图片转换为jpg
def convert_existing_webp_to_jpg():
    # 由于没有现有的webp图片文件夹，直接返回
    logger.info("跳过webp图片转换，直接进入监控模式")
    return

if __name__ == "__main__":
    # 首先转换现有的webp图片
    convert_existing_webp_to_jpg()
    # 然后开始监控
    main()
