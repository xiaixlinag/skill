#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动分析脚本
每小时自动分析微信群聊天记录并推送到 POPO
"""

from __future__ import print_function
from __future__ import unicode_literals
import json
import os
import sys
import codecs
import time
from datetime import datetime

# Python 2/3 兼容
PY2 = sys.version_info[0] == 2
if PY2:
    reload(sys)
    sys.setdefaultencoding('utf-8')
    from urllib2 import urlopen, Request
    from urllib import urlencode
else:
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode

# 脚本目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)

def load_config():
    """加载配置文件"""
    config_file = os.path.join(SKILL_DIR, 'config.json')
    if not os.path.exists(config_file):
        print("[ERROR] config.json not found")
        return None
    with codecs.open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def send_popo_message(webhook_url, keyword, message):
    """发送 POPO 消息"""
    try:
        full_message = "{0} {1}".format(keyword, message)
        data = json.dumps({"message": full_message})
        
        if PY2:
            req = Request(webhook_url, data)
        else:
            req = Request(webhook_url, data.encode('utf-8'))
        
        req.add_header('Content-Type', 'application/json')
        response = urlopen(req, timeout=30)
        result = json.loads(response.read().decode('utf-8'))
        
        if result.get('errcode') == 0:
            print("[OK] POPO message sent successfully")
            return True
        else:
            print("[ERROR] POPO send failed: {0}".format(result.get('errmsg')))
            return False
    except Exception as e:
        print("[ERROR] POPO send error: {0}".format(str(e)))
        return False

def run_analysis(config):
    """运行分析"""
    # 导入分析模块
    sys.path.insert(0, SCRIPT_DIR)
    from analyze import parse_message_file, filter_messages, generate_report, load_learned_rules
    
    # 获取配置
    message_input = config.get('message_input', '../qsec-wechat-export/message.txt')
    group_name = config.get('group_name', '')
    nickname = config.get('nickname', '')
    
    # 处理相对路径
    if not os.path.isabs(message_input):
        message_input = os.path.join(SKILL_DIR, message_input)
    
    # 检查输入文件
    if not os.path.exists(message_input):
        print("[ERROR] Message file not found: {0}".format(message_input))
        return None
    
    # 运行分析
    print("[INFO] Reading messages from: {0}".format(message_input))
    messages = parse_message_file(message_input)
    print("[INFO] Total messages: {0}".format(len(messages)))
    
    print("[INFO] Filtering for group: {0}".format(group_name))
    bug_messages, at_me_messages = filter_messages(messages, group_name, nickname)
    
    print("[OK] Bug messages: {0}".format(len(bug_messages)))
    print("[OK] @me messages: {0}".format(len(at_me_messages)))
    
    # 生成报告
    output_path = os.path.join(SKILL_DIR, 'report.txt')
    report, summary = generate_report(bug_messages, at_me_messages, group_name, output_path)
    
    return {
        'bug_count': len(bug_messages),
        'at_me_count': len(at_me_messages),
        'report': report,
        'summary': summary
    }

def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("🔄 自动分析任务开始")
    print("时间: {0}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    print("=" * 50)
    
    # 加载配置
    config = load_config()
    if not config:
        return 1
    
    # 运行分析
    result = run_analysis(config)
    if not result:
        return 1
    
    # 推送到 POPO
    if config.get('auto_push_to_popo', False):
        webhook = config.get('popo_webhook', '')
        keyword = config.get('popo_keyword', '总结')
        
        if webhook:
            # 构建消息
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            message = "📊 微信群自动分析报告\n"
            message += "时间: {0}\n\n".format(now)
            message += "📌 统计:\n"
            message += "• Bug 消息: {0} 条\n".format(result['bug_count'])
            message += "• @我 消息: {0} 条\n".format(result['at_me_count'])
            
            if result['bug_count'] > 0 or result['at_me_count'] > 0:
                message += "\n详情请查看完整报告"
            else:
                message += "\n✅ 暂无需要处理的消息"
            
            send_popo_message(webhook, keyword, message)
    
    print("\n[OK] 自动分析任务完成")
    print("=" * 50 + "\n")
    
    return 0

def daemon_mode():
    """守护进程模式 - 持续运行，每小时执行一次"""
    config = load_config()
    if not config:
        return 1
    
    interval = config.get('auto_analyze_interval', 3600)
    print("[INFO] Daemon mode started, interval: {0}s".format(interval))
    
    while True:
        try:
            main()
        except Exception as e:
            print("[ERROR] Analysis failed: {0}".format(str(e)))
        
        print("[INFO] Next run in {0} seconds...".format(interval))
        time.sleep(interval)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='自动分析脚本')
    parser.add_argument('--daemon', action='store_true', help='守护进程模式')
    args = parser.parse_args()
    
    if args.daemon:
        daemon_mode()
    else:
        sys.exit(main())