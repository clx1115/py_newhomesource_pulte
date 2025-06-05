import json
import logging
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def is_valid_link(url):
    """检查链接是否以数字结尾"""
    # 移除可能的尾部斜杠
    url = url.rstrip('/')
    # 获取最后一个部分
    last_part = url.split('/')[-1]
    # 检查最后一个字符是否是数字
    return last_part[-1].isdigit() if last_part else False

def main():
    try:
        # 读取现有文件
        with open('pulte_links.json', 'r', encoding='utf-8') as f:
            links = json.load(f)
            
        logger.info(f"原始链接数量: {len(links)}")
        
        # 过滤链接
        filtered_links = [link for link in links if is_valid_link(link)]
        logger.info(f"过滤后链接数量: {len(filtered_links)}")
        
        # 保存过滤后的链接
        with open('pulte_links.json', 'w', encoding='utf-8') as f:
            json.dump(filtered_links, f, indent=2, ensure_ascii=False)
            
        logger.info("已更新 pulte_links.json")
        
    except Exception as e:
        logger.error(f"处理文件时出错: {str(e)}")

if __name__ == "__main__":
    main() 