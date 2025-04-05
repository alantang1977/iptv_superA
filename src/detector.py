#!/usr/bin/env python3
import requests
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlencode, parse_qs
import re
import time
from typing import Dict, Optional, Tuple

class StreamDetector:
    def __init__(self, timeout: int = 10):
        self.session = requests.Session()
        self.timeout = timeout
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })

    def detect_catchup_capability(self, stream_url: str) -> Dict:
        """
        检测直播源的回放能力
        返回结构:
        {
            "supported": bool,
            "max_days": int,    # 最大支持回看天数
            "recommended_template": str,  # 最优回放参数模板
            "latency_ms": int,  # 源站响应延迟
            "codec_info": str   # 流编码信息
        }
        """
        result = {
            "supported": False,
            "max_days": 0,
            "recommended_template": None,
            "latency_ms": 0,
            "codec_info": "unknown"
        }

        # 基础连通性测试
        if not self._test_connection(stream_url):
            return result

        # 检测回放支持天数 (1,3,7,15,30)
        test_days = [1, 3, 7, 15, 30]
        for days in sorted(test_days, reverse=True):
            if self._test_catchup_day(stream_url, days):
                result["max_days"] = days
                result["supported"] = True
                break

        # 检测最优参数模板
        result["recommended_template"] = self._find_best_template(stream_url)

        # 获取流媒体编码信息
        result.update(self._get_stream_metadata(stream_url))

        return result

    def _test_connection(self, url: str) -> bool:
        """基础连通性测试"""
        try:
            start = time.time()
            resp = self.session.head(
                url,
                timeout=self.timeout,
                allow_redirects=True
            )
            result = resp.status_code == 200
            return result
        except:
            return False

    def _test_catchup_day(self, url: str, days: int) -> bool:
        """测试特定天数的回放支持"""
        test_url = self._apply_catchup_params(url, days)
        try:
            resp = self.session.head(
                test_url,
                timeout=self.timeout,
                allow_redirects=True
            )
            # 检查返回状态码和Content-Type
            return (
                resp.status_code == 200 and 
                resp.headers.get("Content-Type", "").startswith(("video/", "application/vnd.apple.mpegurl"))
            )
        except:
            return False

    def _apply_catchup_params(self, url: str, days: int) -> str:
        """应用回放参数到URL"""
        templates = [
            ("playseek={utc}-{utcend}", "utc"),  # 标准模板
            ("timeshift={sec}", "sec"),          # 秒级模板
            ("dvr={days}", "days"),              # 天数模板
            ("utc={start}&end={end}", "range")   # 范围模板
        ]

        now = datetime.utcnow()
        start = now - timedelta(days=days)

        for template, type in templates:
            try:
                if type == "utc":
                    param = template.format(
                        utc=start.strftime("%Y%m%d%H%M%S"),
                        utcend=now.strftime("%Y%m%d%H%M%S")
                    )
                elif type == "sec":
                    param = template.format(sec=days*86400)
                elif type == "days":
                    param = template.format(days=days)
                elif type == "range":
                    param = template.format(
                        start=int(start.timestamp()),
                        end=int(now.timestamp())
                    )

                parsed = urlparse(url)
                query = parse_qs(parsed.query)
                query["catchup"] = [param]
                return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
            except:
                continue

        return url  # 无法应用模板时返回原URL

    def _find_best_template(self, url: str) -> Optional[str]:
        """寻找最优回放参数模板"""
        templates = [
            "playseek={utc}-{utcend}",  # 优先级最高
            "timeshift={sec}",
            "utc={start}&end={end}",
            "dvr={days}"
        ]

        for template in templates:
            test_url = self._apply_template(url, template)
            if self._test_template(test_url):
                return template
        return None

    def _apply_template(self, url: str, template: str) -> str:
        """应用指定模板到URL"""
        now = datetime.utcnow()
        start = now - timedelta(days=1)  # 用1天做测试

        try:
            if "utc" in template:
                param = template.format(
                    utc=start.strftime("%Y%m%d%H%M%S"),
                    utcend=now.strftime("%Y%m%d%H%M%S")
                )
            elif "sec" in template:
                param = template.format(sec=86400)
            elif "days" in template:
                param = template.format(days=1)
            elif "start" in template:
                param = template.format(
                    start=int(start.timestamp()),
                    end=int(now.timestamp())
                )

            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            query["catchup"] = [param]
            return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
        except:
            return url

    def _test_template(self, url: str) -> bool:
        """测试模板有效性"""
        try:
            resp = self.session.head(url, timeout=5)
            return resp.status_code == 200
        except:
            return False

    def _get_stream_metadata(self, url: str) -> Dict:
        """获取流媒体元数据"""
        result = {
            "codec_info": "unknown",
            "latency_ms": 0
        }

        try:
            start = time.time()
            resp = self.session.get(
                url,
                stream=True,
                timeout=self.timeout
            )
            result["latency_ms"] = int((time.time() - start) * 1000)

            # 从响应头解析编码信息
            content_type = resp.headers.get("Content-Type", "")
            if "mpegurl" in content_type:
                result["codec_info"] = "HLS"
            elif "mp2t" in content_type:
                result["codec_info"] = "MPEG-TS"
            elif "flv" in content_type:
                result["codec_info"] = "FLV"
            
            # 尝试从正文解析
            if result["codec_info"] == "unknown":
                sample = next(resp.iter_content(512), b"")
                if b"#EXTM3U" in sample:
                    result["codec_info"] = "HLS"
                elif sample.startswith((b"\x47", b"\x00\x00\x01\xBA")):
                    result["codec_info"] = "MPEG-TS"
        except:
            pass

        return result

# 使用示例
if __name__ == "__main__":
    detector = StreamDetector()
    test_url = "http://example.com/live/stream.m3u8"
    
    report = detector.detect_catchup_capability(test_url)
    print("检测报告:")
    print(f"回放支持: {'是' if report['supported'] else '否'}")
    print(f"最大回看天数: {report['max_days']}天")
    print(f"推荐参数模板: {report['recommended_template']}")
    print(f"流媒体类型: {report['codec_info']}")
    print(f"响应延迟: {report['latency_ms']}ms")
