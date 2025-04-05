from datetime import datetime, timedelta
from src.utils.logger import logger

class M3UGenerator:
    def __init__(self, config):
        self.config = config
    
    def _generate_catchup(self, channel):
        """生成回看参数"""
        if not self.config['tvbox']['catchup']['enable']:
            return channel
        
        days = self.config['tvbox']['catchup']['days']
        template = self.config['tvbox']['catchup']['template']
        
        # 添加回看参数
        if '?' in channel['url']:
            channel['url'] += '&'
        else:
            channel['url'] += '?'
            
        channel['url'] += template
        
        return channel
    
    def generate(self, channels, full_format=False):
        """生成M3U内容"""
        header = "#EXTM3U"
        
        if full_format:
            header += f" x-tvg-url=\"{self.config['tvbox']['epg']}\"\n"
            header += f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        entries = []
        for channel in channels:
            if not full_format:
                channel = self._generate_catchup(channel)
            
            extinf = f"#EXTINF:-1 tvg-id=\"{channel['tvg_id']}\""
            extinf += f" tvg-name=\"{channel['name']}\""
            extinf += f" tvg-logo=\"{channel['logo']}\""
            extinf += f" group-title=\"{channel['group']}\",{channel['name']}"
            
            entries.append(extinf)
            entries.append(channel['url'])
        
        return header + "\n" + "\n".join(entries)
