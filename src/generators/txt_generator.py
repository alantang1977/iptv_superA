#!/usr/bin/env python3
import os
import re
import requests
import concurrent.futures
from urllib.parse import urlparse
from collections import defaultdict
from datetime import datetime

class TXTGenerator:
    def __init__(self):
        self.sources_file = "config/custom_sources.txt"
        self.output_dir = "outputs"
        self.timeout = 15
        self.max_threads = 8
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        self.channels = defaultdict(list)
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def load_sources(self):
        """加载自定义源列表"""
        with open(self.sources_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]

    def fetch_source(self, url):
        """获取单个源内容"""
        try:
            if url.startswith(("http://", "https://")):
                headers = {"User-Agent": self.user_agent}
                resp = requests.get(url, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                return resp.text
            else:  # 本地文件
                with open(url, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            print(f"[ERROR] 获取源失败 {url}: {str(e)}")
            return None

    def parse_m3u(self, content, source_url):
        """解析M3U格式内容"""
        channels = []
        current_channel = {}
        
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("#EXTINF"):
                current_channel = self.parse_extinf(line)
            elif line and not line.startswith("#"):
                if current_channel:
                    current_channel["url"] = self.process_url(line, source_url)
                    channels.append(current_channel)
                    current_channel = {}
                    
        return channels

    def parse_txt(self, content, source_url):
        """解析TXT格式内容"""
        channels = []
        
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            if ",#" in line:
                parts = line.split(",#", 1)
                if len(parts) == 2:
                    name = parts.strip()
                    url = parts.strip()
                    channels.append({
                        "name": name,
                        "url": self.process_url(url, source_url),
                        "group": "Default"
                    })
                    
        return channels

    def parse_extinf(self, line):
        """解析EXTINF行"""
        channel = {
            "name": "",
            "group": "Default",
            "tvg_id": "",
            "logo": ""
        }
        
        # 提取名称
        name_part = line.split(",", 1)
        if len(name_part) > 1:
            channel["name"] = name_part.strip()
            
        # 提取参数
        params = re.findall(r'([a-z-]+)="([^"]*)"', name_part)
        for key, value in params:
            if key == "tvg-id":
                channel["tvg_id"] = value
            elif key == "tvg-logo":
                channel["logo"] = value
            elif key == "group-title":
                channel["group"] = value
                
        return channel

    def process_url(self, url, source_url):
        """处理URL，修复相对路径"""
        if url.startswith(("http://", "https://", "rtmp://", "rtsp://")):
            return url
            
        # 处理相对路径
        if source_url.startswith(("http://", "https://")):
            base_url = "/".join(source_url.split("/")[:-1])
            return f"{base_url}/{url.lstrip('/')}"
            
        return url

    def generate_txt(self):
        """生成简化版TXT文件"""
        txt_path = os.path.join(self.output_dir, "simple_channels.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            for group, channels in self.channels.items():
                for chan in channels:
                    f.write(f"{chan['name']},#{chan['url']}\n")
        print(f"[SUCCESS] 已生成简化版TXT文件: {txt_path}")

    def process_sources(self):
        """处理所有源"""
        sources = self.load_sources()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = []
            
            for source in sources:
                futures.append(executor.submit(self.process_single_source, source))
                
            for future in concurrent.futures.as_completed(futures):
                try:
                    channels = future.result()
                    for chan in channels:
                        self.channels[chan["group"]].append(chan)
                except Exception as e:
                    print(f"[ERROR] 处理源失败: {str(e)}")

    def process_single_source(self, source_url):
        """处理单个源"""
        print(f"[INFO] 正在处理源: {source_url}")
        content = self.fetch_source(source_url)
        if not content:
            return []
            
        if "#EXTM3U" in content[:20]:
            return self.parse_m3u(content, source_url)
        else:
            return self.parse_txt(content, source_url)

if __name__ == "__main__":
    print("=== IPTV TXT生成器 ===")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    generator = TXTGenerator()
    generator.process_sources()
    generator.generate_txt()
    
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=== 执行完毕 ===")
