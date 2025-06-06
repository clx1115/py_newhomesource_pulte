import json
import os
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

def filter_json_files():
    """过滤并删除homeplans和homesites都为空的JSON文件"""
    try:
        # 指定JSON文件目录
        json_dir = 'data/pulte/json'
        
        # 确保目录存在
        if not os.path.exists(json_dir):
            logger.error(f"目录不存在: {json_dir}")
            return
        
        # 获取所有JSON文件
        json_files = [f for f in os.listdir(json_dir) if f.endswith('.json')]
        total_files = len(json_files)
        logger.info(f"找到 {total_files} 个JSON文件")
        
        # 记录删除的文件数
        deleted_count = 0
        
        # 遍历所有JSON文件
        for filename in json_files:
            file_path = os.path.join(json_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 检查homeplans和homesites是否都为空
                if not data.get('homeplans') and not data.get('homesites'):
                    logger.info(f"删除文件 {filename} (homeplans和homesites都为空)")
                    # 删除JSON文件
                    os.remove(file_path)
                    
                    # 同时删除对应的HTML文件
                    html_filename = filename.replace('.json', '.html')
                    html_path = os.path.join('data/pulte/html', html_filename)
                    if os.path.exists(html_path):
                        os.remove(html_path)
                        logger.info(f"删除对应的HTML文件: {html_filename}")
                    
                    deleted_count += 1
                    
            except Exception as e:
                logger.error(f"处理文件 {filename} 时出错: {str(e)}")
                continue
        
        # 输出处理结果
        remaining_files = total_files - deleted_count
        logger.info(f"处理完成:")
        logger.info(f"- 原始文件数: {total_files}")
        logger.info(f"- 删除文件数: {deleted_count}")
        logger.info(f"- 剩余文件数: {remaining_files}")
        
    except Exception as e:
        logger.error(f"执行过程中出错: {str(e)}")
        logger.exception("详细错误信息：")

if __name__ == "__main__":
    filter_json_files() 