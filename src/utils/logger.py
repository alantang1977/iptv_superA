
# src/utils/logger.py

import logging

# 配置日志记录器
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 示例使用
if __name__ == "__main__":
    logger.info("日志记录器已配置并运行。")
