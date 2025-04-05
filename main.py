import json
from pathlib import Path
from src.core.fetcher import SourceFetcher
from src.core.merger import ChannelMerger
from src.generators.m3u_generator import M3UGenerator
from src.generators.txt_generator import TXTGenerator
from src.utils.logger import setup_logger

def load_config():
    with open('config/sources.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    # 初始化日志记录器
    logger = setup_logger(__name__)

    # 加载配置
    config = load_config()
    Path('outputs').mkdir(exist_ok=True)
    
    # 1. 获取所有源
    logger.info("Fetching sources...")
    fetcher = SourceFetcher(config)
    sources_data = fetcher.fetch_all(config['sources'])
    
    # 2. 合并去重
    logger.info("Merging channels...")
    merger = ChannelMerger(config)
    merged_channels = merger.merge(sources_data)
    
    # 3. 生成输出文件
    logger.info("Generating output files...")
    m3u_gen = M3UGenerator(config)
    txt_gen = TXTGenerator()
    
    # TVBox专用格式
    with open('outputs/tvbox.m3u', 'w', encoding='utf-8') as f:
        f.write(m3u_gen.generate(merged_channels, full_format=False))
    
    # 完整M3U
    with open('outputs/full.m3u', 'w', encoding='utf-8') as f:
        f.write(m3u_gen.generate(merged_channels, full_format=True))
    
    # 简化TXT
    with open('outputs/simple.txt', 'w', encoding='utf-8') as f:
        f.write(txt_gen.generate(merged_channels))
    
    logger.info(f"生成完成！共处理 {len(merged_channels)} 个频道")

if __name__ == '__main__':
    main()
