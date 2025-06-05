from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
import time
import logging
import os
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
sys.stdout.reconfigure(encoding='utf-8')  # 设置标准输出编码为UTF-8
logger = logging.getLogger(__name__)

def setup_driver():
    """设置Chrome驱动"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.page_load_strategy = 'eager'
    return webdriver.Chrome(options=chrome_options)

def get_initial_links():
    """获取初始链接列表"""
    url = "https://www.pulte.com/"
    driver = setup_driver()
    initial_links = []
    
    try:
        logger.info("开始获取初始页面...")
        driver.get(url)
        wait = WebDriverWait(driver, 30)
        time.sleep(5)
        
        # 保存初始页面HTML
        os.makedirs('data', exist_ok=True)
        with open('data/pulte_initial.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.info("初始页面HTML已保存")
        
        # 解析页面获取链接
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 查找所有可能包含州链接的元素
        state_links = []
        
        # 方法1：查找list-unstyled类的ul
        ul_elements = soup.find_all('ul', class_='list-unstyled')
        for ul in ul_elements:
            for a in ul.find_all('a', href=True):
                href = a['href']
                if not href.startswith('http'):
                    href = 'https://www.pulte.com' + href
                if '/homes/' in href.lower() and href not in state_links:
                    state_links.append(href)
                    logger.info(f"方法1找到州链接: {href}")
        
        # 方法2：查找所有包含/homes/的链接
        all_links = soup.find_all('a', href=lambda x: x and '/homes/' in x.lower())
        for link in all_links:
            href = link['href']
            if not href.startswith('http'):
                href = 'https://www.pulte.com' + href
            if href not in state_links:
                state_links.append(href)
                logger.info(f"方法2找到州链接: {href}")
        
        initial_links = list(set(state_links))  # 去重
        logger.info(f"总共找到 {len(initial_links)} 个州链接")
        return initial_links
        
    except Exception as e:
        logger.error(f"获取初始链接时出错: {str(e)}")
        return []
    finally:
        driver.quit()

def get_community_links(initial_links):
    """从初始链接获取社区链接"""
    driver = setup_driver()
    community_links = []
    
    try:
        for url in initial_links:
            logger.info(f"处理链接: {url}")
            try:
                driver.get(url)
                time.sleep(5)
                
                # 保存每个页面的HTML（使用URL的最后部分作为文件名）
                filename = url.rstrip('/').split('/')[-1] or 'index'
                with open(f'data/pulte_{filename}.html', 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                
                # 解析页面获取社区链接
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # 方法1：通过ProductSummary__headline类查找
                product_elements = soup.find_all(class_='ProductSummary__headline')
                for element in product_elements:
                    a_tag = element.find('a')
                    if a_tag:
                        href = a_tag.get('data-href') or a_tag.get('href')
                        if href:
                            if not href.startswith('http'):
                                href = 'https://www.pulte.com' + href
                            if href not in community_links:
                                community_links.append(href)
                                logger.info(f"方法1找到社区链接: {href}")
                
                # 方法2：查找所有可能的社区链接
                community_containers = soup.find_all(['div', 'article'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['community', 'product', 'home-item']))
                for container in community_containers:
                    a_tags = container.find_all('a', href=True)
                    for a_tag in a_tags:
                        href = a_tag.get('href')
                        if href and '/homes/' in href.lower():
                            if not href.startswith('http'):
                                href = 'https://www.pulte.com' + href
                            if href not in community_links:
                                community_links.append(href)
                                logger.info(f"方法2找到社区链接: {href}")
            
            except Exception as e:
                logger.error(f"处理链接 {url} 时出错: {str(e)}")
                continue
        
        return list(set(community_links))  # 去重
    except Exception as e:
        logger.error(f"获取社区链接时出错: {str(e)}")
        return []
    finally:
        driver.quit()

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
        # 获取初始链接
        initial_links = get_initial_links()
        logger.info(f"找到 {len(initial_links)} 个初始链接")
        
        if not initial_links:
            logger.error("未找到初始链接")
            return
        
        # 获取社区链接
        community_links = get_community_links(initial_links)
        logger.info(f"找到 {len(community_links)} 个社区链接")
        
        if not community_links:
            logger.error("未找到社区链接")
            return
        
        # 过滤链接，只保留末尾是数字的
        filtered_links = [link for link in community_links if is_valid_link(link)]
        logger.info(f"过滤后剩余 {len(filtered_links)} 个有效链接")
        
        # 保存链接到JSON文件
        with open('pulte_links.json', 'w', encoding='utf-8') as f:
            json.dump(filtered_links, f, indent=2, ensure_ascii=False)
        logger.info("链接已保存到 pulte_links.json")
        
    except Exception as e:
        logger.error(f"主程序执行出错: {str(e)}")

if __name__ == "__main__":
    main() 