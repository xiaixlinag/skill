#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动分析脚本
每小时自动分析微信群聊天记录并推送到 POPO
支持分段发送完整原文
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

# 消息长度限制（POPO 限制约 3000 字符，预留空间）
MAX_MESSAGE_LENGTH = 2500

def load_config():
    """加载配置文件（优先使用 config.local.json）"""
    # 优先使用本地配置（包含敏感信息）
    local_config_file = os.path.join(SKILL_DIR, 'config.local.json')
    config_file = os.path.join(SKILL_DIR, 'config.json')
    
    if os.path.exists(local_config_file):
        with codecs.open(local_config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    elif os.path.exists(config_file):
        with codecs.open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print("[ERROR] No config file found (config.local.json or config.json)")
        return None

def send_popo_message(webhook_url, keyword, message):
    """发送单条 POPO 消息"""
    try:
        full_message = "{0} {1}".format(keyword, message)
        data = json.dumps({"message": full_message})
        
        if PY2:
            req = Request(webhook_url, data)
        else:
            req = Request(webhook_url, data.encode('utf-8'))
        
        req.add_header('Content-Type', 'application/json; charset=utf-8')
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

def send_popo_messages_chunked(webhook_url, keyword, messages_list):
    """分段发送多条 POPO 消息"""
    success_count = 0
    for i, msg in enumerate(messages_list):
        print("[INFO] Sending message {0}/{1}...".format(i + 1, len(messages_list)))
        if send_popo_message(webhook_url, keyword, msg):
            success_count += 1
        # 防止发送过快
        if i < len(messages_list) - 1:
            time.sleep(1)
    return success_count

def format_full_report_messages(bug_messages, at_me_messages, group_name):
    """将完整报告格式化为多条消息（用于分段发送）- 新格式"""
    from analyze import has_reference_message
    
    # 计算时间范围
    all_msgs = bug_messages + at_me_messages
    if all_msgs:
        sorted_msgs = sorted(all_msgs, key=lambda x: x['timestamp'])
        time_start = sorted_msgs[0]['timestamp']
        time_end = sorted_msgs[-1]['timestamp']
    else:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        time_start = now
        time_end = now
    
    messages = []
    
    # 第一条消息：头部信息
    header = "🎮 荒野行动群聊 Bug 监控报告\n"
    header += "⏰ 时间范围：{0} ~ {1}\n".format(time_start, time_end)
    header += "📊 发现 bug 数：{0}\n".format(len(bug_messages))
    header += "=" * 50
    
    # 构建 Bug 消息内容
    current_msg = header
    
    for i, msg in enumerate(sorted(bug_messages, key=lambda x: x['timestamp']), 1):
        content = msg['content'].replace('\n', ' ')  # 完整内容，不截断
        
        # 添加引用标记
        ref_mark = " ⚠️含引用" if has_reference_message(msg['content']) else ""
        
        entry = "\n\n【{0}】{1} @ {2}\n".format(i, msg['sender'], msg['timestamp'])
        entry += "群组：{0}\n".format(msg['group'])
        entry += "内容：{0}{1}\n".format(content, ref_mark)
        entry += "-" * 30
        
        # 检查是否超长，需要分段
        if len(current_msg) + len(entry) > MAX_MESSAGE_LENGTH:
            messages.append(current_msg)
            current_msg = "🎮 Bug 监控报告 (续)\n" + "=" * 50 + entry
        else:
            current_msg += entry
    
    # 添加 @我 的消息
    if at_me_messages:
        at_me_header = "\n\n📢 @我 的消息数：{0}\n".format(len(at_me_messages))
        at_me_header += "=" * 50
        
        if len(current_msg) + len(at_me_header) > MAX_MESSAGE_LENGTH:
            messages.append(current_msg)
            current_msg = at_me_header
        else:
            current_msg += at_me_header
        
        for i, msg in enumerate(sorted(at_me_messages, key=lambda x: x['timestamp']), 1):
            content = msg['content'].replace('\n', ' ')[:200]
            if len(msg['content']) > 200:
                content += '...'
            
            ref_mark = " ⚠️含引用" if has_reference_message(msg['content']) else ""
            
            entry = "\n\n【{0}】{1} @ {2}\n".format(i, msg['sender'], msg['timestamp'])
            entry += "群组：{0}\n".format(msg['group'])
            entry += "内容：{0}{1}\n".format(content, ref_mark)
            entry += "-" * 30
            
            if len(current_msg) + len(entry) > MAX_MESSAGE_LENGTH:
                messages.append(current_msg)
                current_msg = "📢 @我 的消息 (续)\n" + "=" * 50 + entry
            else:
                current_msg += entry
    
    # 添加最后一条消息
    if current_msg:
        messages.append(current_msg)
    
    return messages

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
        'bug_messages': bug_messages,
        'at_me_messages': at_me_messages,
        'group_name': group_name,
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
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            if result['bug_count'] > 0 or result['at_me_count'] > 0:
                # 有内容时推送完整原文报告（分段发送）
                popo_messages = format_full_report_messages(
                    result['bug_messages'],
                    result['at_me_messages'],
                    result['group_name']
                )
                print("[INFO] Will send {0} message(s) to POPO".format(len(popo_messages)))
                send_popo_messages_chunked(webhook, keyword, popo_messages)
            else:
                # 无内容时推送简短消息
                message = "📊 微信群自动分析报告\n"
                message += "时间: {0}\n\n".format(now)
                message += "✅ 暂无需要处理的 Bug 消息或 @我 消息"
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