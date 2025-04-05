#!/usr/bin/env python3
import json
import requests
import hashlib
import concurrent.futures
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import re
import os
from typing import Dict, List, Optional, Tuple

class IPTVGenerator:
    def __init__(self, config_path: str = "config/sources.json"):
        self.config = self._load_config(config_path)
        self.channels: Dict[str, dict] = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.config.get("user_agent", "")})
        
    def _load_config(self, path: str) -> dict:
        """加载配置文件"""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _fetch_source(self, url: str) -> Optional[str]:
        """获取直播源内容"""
        try:
            if url.startswith(("http://", "https://")):
                resp = self.session.get(
                    url, 
                    timeout=self.config.get("timeout", 10),
                    stream=True
                )
                resp.raise_for_status()
                return resp.text
            else:  # 本地文件
                with open(url, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            print(f"[ERROR] 获取源失败 {url}: {str(e)}")
            return None
    
    def _parse_m3u(self, content: str, priority: int) -> List[dict]:
        """解析M3U格式源"""
        channels = []
        current_meta = {}
        
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("#EXTINF"):
                current_meta = self._parse_extinf(line)
                current_meta["priority"] = priority
            elif line and not line.startswith("#"):
                current_meta["url"] = self._process_url(line)
                channels.append(current_meta.copy())
                current_meta.clear()
                
        return channels
    
    def _parse_txt(self, content: str, priority: int) -> List[dict]:
        """解析TXT格式源"""
        channels = []
        
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            if ",#" in line:
                parts = line.split(",#", 1)
                name = parts.strip()
                url = parts.strip()
                
                channels.append({
                    "name": name,
                    "url": self._process_url(url),
                    "group": "Default",
                    "tvg_id": "",
                    "logo": "",
                    "priority": priority
                })
                
        return channels
    
    def _parse_extinf(self, line: str) -> dict:
        """解析EXTINF行"""
        meta = {
            "name": "",
            "group": "Default",
            "tvg_id": "",
            "logo": ""
        }
        
        # 提取名称部分
        name_part = line.split(",", 1)
        if len(name_part) > 1:
            meta["name"] = name_part.strip()
            
        # 提取参数部分
        params_part = name_part
        params = re.findall(r'([a-z-]+)="([^"]*)"', params_part)
        
        for key, value in params:
            if key == "tvg-id":
                meta["tvg_id"] = value
            elif key == "tvg-logo":
                meta["logo"] = value
            elif key == "group-title":
                meta["group"] = value
                
        return meta
    
    def _process_url(self, url: str) -> str:
        """处理URL，添加回看参数"""
        if not self.config.get("catchup", {}).get("enable", False):
            return url
            
        days = self.config["catchup"].get("days", 3)
        if days <= 0:
            return url
            
        # 解析URL
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        
        # 添加回看参数
        catchup_format = self.config["catchup"].get("format", "playseek={utc}-{utcend}")
        query["playseek"] = [catchup_format]
        
        # 重建URL
        new_query = urlencode(query, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    
    def _channel_key(self, channel: dict) -> str:
        """生成频道唯一键"""
        key_str = f"{channel['group']}|{channel['name']}|{channel['tvg_id']}"
        return hashlib.md5(key_str.encode("utf-8")).hexdigest()
    
    def process_sources(self):
        """处理所有直播源"""
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("threads", 4)
        ) as executor:
            futures = []
            
            for source in self.config["sources"]:
                futures.append(executor.submit(
                    self._process_single_source,
                    source["url"],
                    source.get("type", "auto"),
                    source.get("priority", 50),
                    source.get("name", "")
                ))
                
            for future in concurrent.futures.as_completed(futures):
                try:
                    channels = future.result()
                    for chan in channels:
                        chan_id = self._channel_key(chan)
                        existing = self.channels.get(chan_id)
                        
                        # 保留高优先级源
                        if not existing or existing["priority"] < chan["priority"]:
                            self.channels[chan_id] = chan
                except Exception as e:
                    print(f"[ERROR] 处理源失败: {str(e)}")
    
    def _process_single_source(
        self, 
        url: str, 
        src_type: str, 
        priority: int,
        source_name: str
    ) -> List[dict]:
        """处理单个直播源"""
        print(f"[INFO] 正在处理源: {source_name} ({url})")
        content = self._fetch_source(url)
        if not content:
            return []
            
        if src_type == "auto":
            src_type = "m3u" if "#EXTM3U" in content[:20] else "txt"
            
        if src_type == "m3u":
            return self._parse_m3u(content, priority)
        else:
            return self._parse_txt(content, priority)
    
    def generate_m3u(self) -> str:
        """生成M3U文件内容"""
        header = f"""#EXTM3U x-tvg-url="{self.config.get('epg_url', '')}"
# Generated by IPTV Generator on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Catchup: {"Enabled" if self.config.get("catchup", {}).get("enable", False) else "Disabled"}
"""
        entries = []
        
        for chan in self.channels.values():
            extinf = f'#EXTINF:-1 tvg-id="{chan["tvg_id"]}" tvg-name="{chan["name"]}"'
            extinf += f' tvg-logo="{chan["logo"]}" group-title="{chan["group"]}",{chan["name"]}'
            entries.append(extinf)
            entries.append(chan["url"])
            
        return header + "\n".join(entries)
    
    def generate_simplified(self) -> str:
        """生成简化版TXT列表"""
        return "\n".join(
            f"{chan['name']},#{chan['url']}" 
            for chan in self.channels.values()
        )
    
    def save_files(self):
        """保存生成的文件"""
        os.makedirs("output", exist_ok=True)
        
        with open("output/playlist.m3u", "w", encoding="utf-8") as f:
            f.write(self.generate_m3u())
            
        with open("output/simplified.txt", "w", encoding="utf-8") as f:
            f.write(self.generate_simplified())

if __name__ == "__main__":
    generator = IPTVGenerator()
    generator.process_sources()
    generator.save_files()
    print("[SUCCESS] 直播源生成完成!")
