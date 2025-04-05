#!/usr/bin/env python3
import re
from typing import List

def validate_m3u(file_path: str) -> List[str]:
    """验证M3U文件格式"""
    errors = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    if not lines.startswith("#EXTM3U"):
        errors.append("M3U文件缺少EXTM3U头")
        
    extinf_count = 0
    url_count = 0
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("#EXTINF"):
            extinf_count += 1
            if not re.search(r'group-title="[^"]+"', line):
                errors.append(f"第{i}行: 缺少group-title属性")
        elif not line.startswith("#"):
            url_count += 1
            
    if extinf_count != url_count:
        errors.append(f"EXTINF数量({extinf_count})与URL数量({url_count})不匹配")
        
    return errors

if __name__ == "__main__":
    m3u_errors = validate_m3u("output/playlist.m3u")
    if m3u_errors:
        print("[ERROR] M3U文件验证失败:")
        for error in m3u_errors:
            print(f"  - {error}")
        exit(1)
    else:
        print("[SUCCESS] 所有文件验证通过")
