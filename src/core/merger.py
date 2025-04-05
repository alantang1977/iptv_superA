import re
from collections import defaultdict
import hashlib
from src.utils.logger import logger

class ChannelMerger:
    def __init__(self, config):
        self.config = config
        self.channel_map = defaultdict(list)
        
    def _generate_channel_id(self, channel):
        """生成基于频道名称和分组的唯一ID"""
        key = f"{channel.get('name', '')}|{channel.get('group', '')}"
        return hashlib.md5(key.encode('utf-8')).hexdigest()
    
    def _parse_extinf(self, line):
        """解析EXTINF行"""
        channel = {
            'name': '',
            'group': 'Other',
            'tvg_id': '',
            'logo': '',
            'duration': -1,
            'url': ''
        }
        
        # 提取名称
        if ', ' in line:
            channel['name'] = line.split(', ').strip()
        
        # 提取属性
        attrs = re.findall(r'([a-zA-Z0-9-]+)="([^"]*)"', line)
        for attr, value in attrs:
            if attr == 'group-title':
                channel['group'] = value
            elif attr == 'tvg-id':
                channel['tvg_id'] = value
            elif attr == 'tvg-logo':
                channel['logo'] = value
            elif attr == 'duration':
                channel['duration'] = int(value)
        
        return channel
    
    def parse_m3u(self, content, source_url):
        """解析单个M3U内容"""
        channels = []
        current_channel = None
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('#EXTINF'):
                current_channel = self._parse_extinf(line)
            elif current_channel and not line.startswith('#'):
                current_channel['url'] = line
                current_channel['source'] = source_url
                channels.append(current_channel)
                current_channel = None
        
        return channels
    
    def merge(self, sources_data):
        """合并所有源"""
        all_channels = []
        
        for url, content in sources_data.items():
            try:
                channels = self.parse_m3u(content, url)
                all_channels.extend(channels)
            except Exception as e:
                logger.error(f"Error parsing {url}: {str(e)}")
        
        # 去重处理
        unique_channels = {}
        for channel in all_channels:
            channel_id = self._generate_channel_id(channel)
            
            # 保留最高质量的源
            if channel_id not in unique_channels or \
               len(channel['url']) > len(unique_channels[channel_id]['url']):
                unique_channels[channel_id] = channel
        
        # 应用过滤器
        return self._apply_filters(list(unique_channels.values()))
    
    def _apply_filters(self, channels):
        """应用配置的过滤器"""
        filtered = []
        filters = self.config['filters']
        
        for channel in channels:
            # 检查持续时间
            if filters['min_duration'] > 0 and 0 < channel['duration'] < filters['min_duration']:
                continue
                
            # 检查扩展名
            url = channel['url'].lower()
            if not any(url.endswith(ext) for ext in filters['allowed_extensions']):
                continue
                
            filtered.append(channel)
        
        return filtered
