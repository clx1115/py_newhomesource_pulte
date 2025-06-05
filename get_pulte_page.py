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
from datetime import datetime
import re
import argparse
import os.path
global_url=""

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
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
    return webdriver.Chrome(options=chrome_options)

def extract_price(text):
    """从文本中提取价格"""
    if not text:
        return None
    price_match = re.search(r'\$[\d,]+', text)
    return price_match.group(0) if price_match else None

def extract_beds_baths(text):
    """从文本中提取卧室和浴室数量"""
    if not text:
        return None, None
    beds_match = re.search(r'(\d+)\s*(?:Bedroom|Bed|BR)', text)
    baths_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:Bathroom|Bath|BA)', text)
    beds = beds_match.group(1) if beds_match else None
    baths = baths_match.group(1) if baths_match else None
    return beds, baths

def extract_sqft(text):
    """从文本中提取平方英尺"""
    if not text:
        return None
    sqft_match = re.search(r'([\d,]+)\s*sq\s*ft', text.lower())
    return sqft_match.group(1).replace(',', '') if sqft_match else None

def fetch_page(url, output_dir='data/pulte'):
    """获取页面数据并解析"""
    try:
        # 生成输出文件名
        community_name = url.split('/')[-1]
        json_file = f"{output_dir}/json/pulte_{community_name}.json"
        
        # 检查文件是否已存在
        if os.path.exists(json_file):
            logger.info(f"JSON文件已存在: {json_file}, 跳过处理...")
            return None
            
        logger.info(f"正在处理URL: {url}")
        driver = setup_driver()
        driver.get(url)
        time.sleep(5)  # 等待页面加载
        global global_url
        global_url=url
        
        # 保存HTML
        os.makedirs(f"{output_dir}/html", exist_ok=True)
        os.makedirs(f"{output_dir}/json", exist_ok=True)
        html_file = f"{output_dir}/html/pulte_{community_name}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.info(f"HTML已保存到: {html_file}")

        # 解析数据
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        data = {
            "timestamp": datetime.now().isoformat(),
            "name": soup.find('h1').text.strip() if soup.find('h1') else None,
            "status": None,
            "url": global_url,
            "price_from": None,
            "address": None,
            "phone": None,
            "description": None,
            "images": [],
            "location": {
                "latitude": None,
                "longitude": None,
                "address": {
                    "city": None,
                    "state": None,
                    "market": None
                }
            },
            "details": {
                "price_range": None,
                "sqft_range": None,
                "bed_range": None,
                "bath_range": None,
                "stories_range": None,
                "community_count": None
            },
            "amenities": [],
            "homeplans": [],
            "homesites": [],
            "nearbyplaces": [],
            "collections": []
        }

        # 提取图片
        # 首先找到所有owl-item active元素
        owl_items = soup.find_all('div', class_='owl-item active')
        logger.info(f"找到 {len(owl_items)} 个owl-item active元素")

        for item in owl_items:
            # 直接在owl-item active下查找class="u-responsiveMedia"的img标签
            responsive_img = item.find('img', class_='u-responsiveMedia')
            if responsive_img and responsive_img.get('src'):
                src = responsive_img['src']
                logger.info(f"找到图片src: {src}")
                # 如果src以//开头，添加https:前缀
                if src.startswith('//'):
                    src = 'https:' + src
                    logger.info(f"添加https:前缀后的src: {src}")
                data["images"].append(src)
            else:
                logger.info("未找到u-responsiveMedia图片元素或src属性")

        logger.info(f"总共提取到 {len(data['images'])} 张图片")

        # 提取经纬度
        # 查找包含经纬度的script标签
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # 查找latitude
                lat_match = re.search(r'latitude["\s:]+([-\d.]+)', script.string)
                if lat_match:
                    data["location"]["latitude"] = float(lat_match.group(1))

                # 查找longitude
                lng_match = re.search(r'longitude["\s:]+([-\d.]+)', script.string)
                if lng_match:
                    data["location"]["longitude"] = float(lng_match.group(1))

        # 提取基本信息
        # 价格信息
        price_elem = soup.find('div', class_=lambda x: x and 'price' in x.lower())
        if price_elem:
            data["price_from"] = extract_price(price_elem.text)

        # 提取amenities信息
        neighborhood_container = soup.find('div', class_='neighborhood-features-container')
        if neighborhood_container:
            logger.info("找到neighborhood-features-container元素")
            neighborhood_items = neighborhood_container.find_all('div', class_='neighborhood-item')
            for item in neighborhood_items:
                li_elements = item.find_all('li')
                for li in li_elements:
                    if li.text.strip():
                        # 提取描述文本
                        description = li.text.strip()

                        # 智能提取关键字作为name
                        # 移除数字开头的部分
                        name_text = re.sub(r'^\d+\s*', '', description)
                        # 提取主要特征词
                        if "Home" in name_text:
                            name = "Home Designs"
                        elif "Floor" in name_text:
                            name = "Floor Plans"
                        elif any(word in name_text for word in ["Square", "Sq", "sq.ft"]):
                            name = "Square Footage"
                        elif "Bath" in name_text:
                            name = "Bathrooms"
                        elif "Bed" in name_text:
                            name = "Bedrooms"
                        elif "Stories" in name_text or "story" in name_text.lower():
                            name = "Stories"
                        elif "Price" in name_text:
                            name = "Price Range"
                        else:
                            # 如果没有匹配到特定关键词，取前两个有意义的词（排除冠词等）
                            words = [w for w in name_text.split() if len(w) > 2 and w.lower() not in ['the', 'and', 'or', 'with', 'from']]
                            name = ' '.join(words[:2]) if words else name_text[:30]

                        amenity = {
                            "name": name,
                            "description": description,
                            "icon_url": None
                        }
                        data["amenities"].append(amenity)
                        logger.info(f"添加amenity - name: {name}, description: {description}")

        logger.info(f"总共提取到 {len(data['amenities'])} 个amenities")

        # 地址信息
        address_elem = soup.find('div', class_=lambda x: x and 'address' in x.lower())
        if address_elem:
            data["address"] = address_elem.text.strip()

        # 电话信息
        phone_elem = soup.find('a', href=lambda x: x and 'tel:' in x)
        if phone_elem:
            data["phone"] = phone_elem.text.strip()

        # 描述信息
        desc_elem = soup.find('div', class_=lambda x: x and ('description' in x.lower() or 'overview' in x.lower()))
        if desc_elem:
            data["description"] = desc_elem.text.strip()

        # 户型信息
        glance_section = soup.find('div', class_='GlanceViewSection')
        if glance_section:
            logger.info("找到GlanceViewSection元素")

            # 直接查找所有homeplan相关元素，不通过col-sm-12
            home_titles = soup.find_all('div', class_='HomeDesignCompactListView__homeTitle')
            logger.info(f"找到 {len(home_titles)} 个HomeDesignCompactListView__homeTitle元素")

            for title_elem in home_titles:
                a_tag = title_elem.find('a')
                if a_tag:
                    # 获取父元素，用于查找相关信息
                    parent_elem = title_elem.parent
                    while parent_elem and 'col-sm-12' not in (parent_elem.get('class') or []):
                        parent_elem = parent_elem.parent

                    if parent_elem:
                        plan = {
                            "name": a_tag.text.strip(),
                            "url": f"https://www.pulte.com{a_tag['href']}" if a_tag.get('href') else None,
                            "details": {
                                "price": None,
                                "beds": None,
                                "baths": None,
                                "half_baths": None,
                                "sqft": None,
                                "status": "Actively selling",
                                "image_url": None
                            },
                            "floorplan_images": None
                        }

                        logger.info(f"正在处理homeplan: {plan['name']}")

                        # 提取价格
                        price_elem = parent_elem.find('div', class_='HomeDesignCompactListView__startingPrice')
                        if price_elem:
                            price_text = price_elem.text.strip()
                            price_match = re.search(r'\$[\d,]+', price_text)
                            if price_match:
                                plan["details"]["price"] = f"From {price_match.group(0)}"
                                logger.info(f"找到价格: {plan['details']['price']}")

                        # 提取卧室数
                        beds_elem = parent_elem.find('div', class_='HomeDesignCompactListView__bedrooms')
                        if beds_elem:
                            beds_match = re.search(r'((?:\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?))(?=\s*Bed)', beds_elem.text)
                            if beds_match:
                                plan["details"]["beds"] = f"{beds_match.group(1)} bd"
                                logger.info(f"找到卧室数: {plan['details']['beds']}")

                        # 提取浴室数
                        baths_elem = parent_elem.find('div', class_='HomeDesignCompactListView__bathrooms')
                        if baths_elem:
                            baths_match = re.search(r'((?:\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?))(?=\s*Bath)', baths_elem.text)
                            if baths_match:
                                plan["details"]["baths"] = f"{baths_match.group(1)} ba"
                                logger.info(f"找到浴室数: {plan['details']['baths']}")

                        # 提取平方英尺
                        sqft_elem = parent_elem.find('div', class_='HomeDesignCompactListView__squareFeet')
                        if sqft_elem:
                            # 修改正则表达式以更准确地提取平方英尺数值
                            sqft_text = sqft_elem.text.strip()
                            logger.info(f"找到原始平方英尺文本: {sqft_text}")
                            # 匹配数字，包括逗号、加号和范围
                            sqft_match = re.search(r'((?:\d{1,3}(?:,\d{3})*(?:\+)?(?:\s*-\s*\d{1,3}(?:,\d{3})*(?:\+)?)?))(?=\s*Sq)', sqft_text)
                            if sqft_match:
                                # 保留逗号和加号，只在范围中间添加连字符
                                sqft_value = sqft_match.group(1).strip()
                                plan["details"]["sqft"] = f"{sqft_value} ft²"
                                logger.info(f"处理后的平方英尺: {plan['details']['sqft']}")
                            else:
                                logger.warning(f"无法从文本中提取平方英尺: {sqft_text}")
                        else:
                            logger.warning("未找到平方英尺元素")

                        # 提取图片URL
                        try:
                            img_src_elem = parent_elem.find('div', class_='HomeDesignCompactListView__homeImage')
                            if img_src_elem:
                                # 在HomeDesignCompactListView__homeImage查找img标签
                                img = img_src_elem.find('img')
                                if img and img.get('data-csrc'):
                                    img_src = img['data-csrc']
                                    # 处理URL前缀
                                    if img_src.startswith('//'):
                                        img_src = f"https:{img_src}"
                                    elif not img_src.startswith('http'):
                                        img_src = f"https://www.pulte.com{img_src}"
                                    plan["details"]["image_url"] = img_src
                                    logger.info(f"找到图片URL: {plan['details']['image_url']}")
                                else:
                                    logger.warning("未找到img标签或src属性")
                                    plan["details"]["image_url"] = None
                            else:
                                logger.warning("未找到HomeDesignCompactListView__homeImage")
                                plan["details"]["image_url"] = None
                        except Exception as e:
                            logger.error(f"提取图片URL时出错: {str(e)}")
                            plan["details"]["image_url"] = None

                        data["homeplans"].append(plan)

                        # 同时创建对应的homesite
                        homesite = {
                            "name": None,
                            "plan": plan["name"],
                            "id": None,  # 稍后设置
                            "address": None,
                            "price": plan["details"]["price"].replace("From ", "") if plan["details"]["price"] else None,
                            "beds": plan["details"]["beds"],
                            "baths": plan["details"]["baths"],
                            "sqft": plan["details"]["sqft"],
                            "status": "Available",
                            "image_url": plan["details"]["image_url"],
                            "url": plan["url"],
                            "latitude": None,
                            "longitude": None,
                            "overview": None,
                            "images": []
                        }

                        # 提取ID：从URL最后一段获取数字，如果没有就用当前homesites的长度+1
                        url_last_segment = homesite['url'].split('/')[-1]
                        id_match = re.search(r'(\d+)', url_last_segment)
                        if id_match:
                            homesite['id'] = id_match.group(1)
                            logger.info(f"从URL提取到ID: {homesite['id']}")
                        else:
                            homesite['id'] = str(len(data['homesites']) + 1)
                            logger.info(f"使用索引作为ID: {homesite['id']}")

                        # 访问homesite的URL获取额外信息
                        try:
                            logger.info(f"正在获取homesite额外信息: {homesite['url']}")
                            # 创建新的driver实例
                            homesite_driver = setup_driver()
                            homesite_driver.get(homesite['url'])
                            time.sleep(5)  # 等待页面加载

                            # 保存HTML
                            plan_name = homesite['url'].split('/')[-1]
                            html_file = f"{output_dir}/html/pulte_{plan_name}.html"
                            with open(html_file, 'w', encoding='utf-8') as f:
                                f.write(homesite_driver.page_source)
                            logger.info(f"Homesite HTML已保存到: {html_file}")

                            # 解析HTML
                            homesite_soup = BeautifulSoup(homesite_driver.page_source, 'html.parser')

                            # 提取地址
                            address_elem = homesite_soup.find('div', class_='CommunityPersistentNav__address')
                            if address_elem:
                                full_address = address_elem.text.strip()
                                # 移除邮编（假设邮编在最后并且是5位数字）
                                homesite['address'] = re.sub(r'\s+\d{5}$', '', full_address)
                                homesite['name'] = homesite['address'].split(',')[0].strip()  # 取地址的第一部分作为name
                                logger.info(f"找到homesite地址: {homesite['address']}")

                            # 提取overview
                            overview_elem = homesite_soup.find('div', class_=lambda x: x and ('description' in x.lower() or 'overview' in x.lower()))
                            if overview_elem:
                                homesite['overview'] = overview_elem.text.strip()
                                logger.info(f"找到homesite概述")

                            # 提取经纬度 - 在整个HTML中搜索
                            html_content = homesite_driver.page_source

                            # 查找latitude - 匹配 "Latitude":"27.3646311523029" 格式
                            lat_match = re.search(r'"Latitude"\s*:\s*"([-\d.]+)"', html_content)
                            if not lat_match:
                                # 尝试其他可能的格式
                                lat_match = re.search(r'latitude["\s:]+([-\d.]+)', html_content)

                            if lat_match:
                                homesite["latitude"] = float(lat_match.group(1))
                                logger.info(f"找到latitude: {homesite['latitude']}")
                            else:
                                logger.warning("未找到latitude")

                            # 查找longitude - 匹配 "Longitude":"-82.3959473004829" 格式
                            lng_match = re.search(r'"Longitude"\s*:\s*"([-\d.]+)"', html_content)
                            if not lng_match:
                                # 尝试其他可能的格式
                                lng_match = re.search(r'longitude["\s:]+([-\d.]+)', html_content)

                            if lng_match:
                                homesite["longitude"] = float(lng_match.group(1))
                                logger.info(f"找到longitude: {homesite['longitude']}")
                            else:
                                logger.warning("未找到longitude")

                            # 提取楼层平面图
                            floor_container = homesite_soup.find_all('div', class_='floor-container')
                            if floor_container:
                                # 查找所有figure标签下的img
                                floor_plan_images = []
                                for idx, figure in enumerate(floor_container, 0):
                                    floor_images = figure.find("figure")
                                    logger.info(f"找到 {len(floor_images)} 个floor-container元素")
                                    img = floor_images.find('img')
                                    if img:
                                        # 依次检查data-csrc、data-src和src属性
                                        img_src = img.get('data-csrc') or img.get('data-src') or img.get('src')
                                        if img_src:
                                            # 处理URL前缀
                                            if img_src.startswith('//'):
                                                img_src = f"https:{img_src}"
                                            elif not img_src.startswith('http'):
                                                img_src = f"https://www.pulte.com{img_src}"

                                            # 创建楼层平面图对象
                                            floor_plan = {
                                                "name": f"{idx+1}{'st' if idx == 0 else 'nd' if idx == 1 else 'rd' if idx == 2 else 'th'} Floor Floorplan",
                                                "url": img_src
                                            }
                                            floor_plan_images.append(floor_plan)
                                            logger.info(f"添加楼层平面图: {floor_plan['name']}")

                                if floor_plan_images:
                                    # 在homeplans数组中找到对应的plan并更新
                                    for p in data["homeplans"]:
                                        if p["name"] == homesite["plan"]:
                                            p["floorplan_images"] = floor_plan_images
                                            logger.info(f"更新plan '{p['name']}'的floorplan_images数组，共{len(floor_plan_images)}个楼层平面图")
                                            break
                            else:
                                logger.warning("未找到floor-container元素")

                            # 提取图片数组
                            owl_stage = homesite_soup.find('div', class_='owl-stage')
                            if owl_stage:
                                owl_items = owl_stage.find_all('div', class_='owl-item')
                                logger.info(f"找到 {len(owl_items)} 个owl-item元素")

                                for item in owl_items:
                                    img = item.find('img')
                                    if img and img.get('data-csrc'):
                                        img_src = img['data-csrc']
                                        # 处理URL前缀
                                        if img_src.startswith('//'):
                                            img_src = f"https:{img_src}"
                                        elif not img_src.startswith('http'):
                                            img_src = f"https://www.pulte.com{img_src}"
                                        homesite["images"].append(img_src)
                                        logger.info(f"添加图片URL到images数组: {img_src}")
                                    elif img and img.get('data-src'):
                                        img_src = img['data-src']
                                        # 处理URL前缀
                                        if img_src.startswith('//'):
                                            img_src = f"https:{img_src}"
                                        elif not img_src.startswith('http'):
                                            img_src = f"https://www.pulte.com{img_src}"
                                        homesite["images"].append(img_src)
                                        logger.info(f"添加图片URL到images数组: {img_src}")
                            else:
                                logger.warning("未找到owl-stage元素")

                            logger.info(f"总共提取到 {len(homesite['images'])} 张图片")

                            homesite_driver.quit()

                        except Exception as e:
                            logger.error(f"获取homesite额外信息时出错: {str(e)}")

                        data["homesites"].append(homesite)
                        logger.info(f"添加homesite for plan: {homesite['plan']}")

            logger.info(f"总共提取到 {len(data['homeplans'])} 个homeplans和 {len(data['homesites'])} 个homesites")

            # 计算details的范围值
            if data['homesites']:
                # 提取价格范围
                prices = []
                beds = []
                baths = []
                sqft = []

                for homesite in data['homesites']:
                    # 处理价格
                    if homesite['price']:
                        price_match = re.search(r'\$([\d,]+)', homesite['price'])
                        if price_match:
                            prices.append(int(price_match.group(1).replace(',', '')))

                    # 处理卧室数
                    if homesite['beds']:
                        bed_match = re.search(r'(\d+)(?:\s*-\s*(\d+))?', homesite['beds'])
                        if bed_match:
                            if bed_match.group(2):  # 如果有范围
                                beds.append(int(bed_match.group(1)))  # 最小值
                                beds.append(int(bed_match.group(2)))  # 最大值
                            else:
                                beds.append(int(bed_match.group(1)))

                    # 处理浴室数
                    if homesite['baths']:
                        bath_match = re.search(r'([\d.]+)(?:\s*-\s*([\d.]+))?', homesite['baths'])
                        if bath_match:
                            if bath_match.group(2):  # 如果有范围
                                baths.append(float(bath_match.group(1)))  # 最小值
                                baths.append(float(bath_match.group(2)))  # 最大值
                            else:
                                baths.append(float(bath_match.group(1)))

                    # 处理平方英尺
                    if homesite['sqft']:
                        sqft_match = re.search(r'(\d+(?:,\d{3})*)(?:\+)?(?:\s*-\s*(\d+(?:,\d{3})*)(?:\+)?)?', homesite['sqft'])
                        if sqft_match:
                            if sqft_match.group(2):  # 如果有范围
                                sqft.append(int(sqft_match.group(1).replace(',', '')))  # 最小值
                                sqft.append(int(sqft_match.group(2).replace(',', '')))  # 最大值
                            else:
                                sqft.append(int(sqft_match.group(1).replace(',', '')))

                # 设置范围值
                if prices:
                    min_price = min(prices)
                    max_price = max(prices)
                    if min_price == max_price:
                        data['details']['price_range'] = f"${min_price:,}"
                    else:
                        data['details']['price_range'] = f"${min_price:,}-${max_price:,}"
                    logger.info(f"价格范围: {data['details']['price_range']}")

                if beds:
                    min_beds = min(beds)
                    max_beds = max(beds)
                    if min_beds == max_beds:
                        data['details']['bed_range'] = str(min_beds)
                    else:
                        data['details']['bed_range'] = f"{min_beds}-{max_beds}"
                    logger.info(f"卧室范围: {data['details']['bed_range']}")

                if baths:
                    min_baths = min(baths)
                    max_baths = max(baths)
                    if min_baths == max_baths:
                        data['details']['bath_range'] = str(min_baths)
                    else:
                        data['details']['bath_range'] = f"{min_baths}-{max_baths}"
                    logger.info(f"浴室范围: {data['details']['bath_range']}")

                if sqft:
                    min_sqft = min(sqft)
                    max_sqft = max(sqft)
                    if min_sqft == max_sqft:
                        data['details']['sqft_range'] = f"{min_sqft:,}"
                    else:
                        data['details']['sqft_range'] = f"{min_sqft:,}-{max_sqft:,}"
                    logger.info(f"平方英尺范围: {data['details']['sqft_range']}")

                # 计算stories_range基于floorplan_images数组长度
                stories = []
                for plan in data['homeplans']:
                    if plan.get('floorplan_images'):  # 确保floorplan_images存在且非null
                        stories.append(len(plan['floorplan_images']))
                
                if stories:  # 如果找到了任何楼层数据
                    min_stories = min(stories)
                    max_stories = max(stories)
                    if min_stories == max_stories:
                        data['details']['stories_range'] = str(max_stories)
                    else:
                        data['details']['stories_range'] = f"{min_stories}-{max_stories}"
                    logger.info(f"楼层范围: {data['details']['stories_range']}")
                else:
                    logger.warning("未找到有效的楼层数据")
                    data['details']['stories_range'] = None

                # 设置community_count
                data['details']['community_count'] = 1
                logger.info("设置community_count为1")

        else:
            logger.warning("未找到GlanceViewSection元素")

        # 保存JSON
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"数据已保存到: {json_file}")

        return data

    except Exception as e:
        logger.error(f"处理页面时出错: {str(e)}")
        return None
    finally:
        driver.quit()

def main():
    """主函数"""
    try:
        # 解析命令行参数
        parser = argparse.ArgumentParser(description='Scrape Pulte community pages')
        parser.add_argument('--batch', action='store_true', help='Process all URLs from pulte_links.json')
        parser.add_argument('--url', help='Process a single URL')
        args = parser.parse_args()

        # 确保输出目录存在
        output_dir = 'data/pulte'
        html_dir = f'{output_dir}/html'
        json_dir = f'{output_dir}/json'
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(html_dir, exist_ok=True)
        os.makedirs(json_dir, exist_ok=True)
        
        if args.batch:
            try:
                # 检查多个可能的文件位置
                current_dir = os.path.dirname(os.path.abspath(__file__))
                possible_paths = [
                    'pulte_links.json',
                    'data/pulte_links.json',
                    'data/pulte/pulte_links.json',
                    os.path.join(current_dir, 'pulte_links.json'),
                    os.path.join(current_dir, 'data/pulte_links.json'),
                    os.path.join(current_dir, 'data/pulte/pulte_links.json')
                ]
                
                json_file = None
                for path in possible_paths:
                    if os.path.exists(path):
                        json_file = path
                        logger.info(f"找到 pulte_links.json 文件位置: {path}")
                        break
                
                if not json_file:
                    logger.error("在所有预期位置都未找到 pulte_links.json")
                    return
                
                # 读取 pulte_links.json
                with open(json_file, 'r', encoding='utf-8') as f:
                    urls = json.load(f)
                
                if not urls:
                    logger.error("pulte_links.json 中没有找到URL")
                    return
                
                logger.info(f"找到 {len(urls)} 个待处理的URL")
                
                # 处理每个URL
                for i, url in enumerate(urls, 1):
                    try:
                        logger.info(f"正在处理第 {i}/{len(urls)} 个URL")
                        fetch_page(url, output_dir)
                        time.sleep(2)  # 添加延迟以避免请求过于频繁
                    except Exception as e:
                        logger.error(f"处理URL失败 {url}: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"批量处理过程中出错: {str(e)}")
                logger.exception("详细错误信息：")
                return
                
        elif args.url:
            # 处理单个指定的URL
            fetch_page(args.url, output_dir)
        else:
            # 处理单个默认URL
            default_urls = [
                "https://www.pulte.com/homes/nevada/las-vegas/las-vegas/monument-at-reverence-211219",
                "https://www.pulte.com/homes/south-carolina/hilton-head/bluffton/malind-bluff-210500",
                "https://www.pulte.com/homes/florida/fort-myers/estero/verdana-village-210715"
            ]
            default_url = default_urls[0]  # 使用第一个URL作为默认值
            fetch_page(default_url, output_dir)
        
    except Exception as e:
        logger.error(f"主程序执行出错: {str(e)}")
        logger.exception("详细错误信息：")

if __name__ == "__main__":
    main() 
