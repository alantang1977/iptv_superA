import logging

def setup_logger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    return logger

# 示例使用
if __name__ == "__main__":
    logger = setup_logger(__name__)
    logger.info("Logger is configured and running.")
