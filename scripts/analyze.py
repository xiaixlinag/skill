#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
微信群 Bug 反馈分析器
分析微信聊天记录，筛选 bug 反馈和 @我 的消息
兼容 Python 2.7 和 Python 3
"""

from __future__ import print_function
from __future__ import unicode_literals
import argparse
import re
from datetime import datetime
import os
import sys
import codecs

# Python 2/3 兼容
PY2 = sys.version_info[0] == 2
if PY2:
    reload(sys)
    sys.setdefaultencoding('utf-8')

# === Bug 检测配置 ===

# 高优先级关键词 - 单独出现即视为 bug 反馈
BUG_KEYWORDS_HIGH = [
    'bug', 'BUG', 'Bug',
    u'报错', u'错误代码', u'异常',
    u'崩溃', u'闪退', u'卡死', u'死机', u'白屏', u'黑屏', u'闪屏',
    u'打不开', u'进不去', u'用不了', u'没反应', u'不响应',
    u'修复', u'修一下',
]

# 问题描述词 - 需要与功能词组合使用
BUG_PROBLEM_WORDS = [
    u'有时候', u'有时', u'偶尔', u'时有时无', u'不稳定',
    u'不显示', u'没显示', u'显示不出', u'看不到',
    u'消失', u'不见了', u'丢失', u'没了',
    u'不能', u'无法', u'失败',
    u'不正常', u'有问题', u'出问题',
]

# 功能/场景词 - 需要与问题词组合使用
BUG_FEATURE_WORDS = [
    u'回放', u'淘汰', u'撤离', u'复活',
    u'抓虫', u'女仆', u'突围', u'经典',
    u'登录', u'加载', u'匹配', u'连接',
    u'道具', u'皮肤', u'装备', u'背包',
    u'声音', u'画面', u'界面', u'按钮',
]

# Bug 报告句式模式 (正则表达式)
BUG_PATTERNS = [
    r'有时候.{0,10}有时候',  # "有时候有...有时候没有" 模式
    r'(打|玩).{0,15}(显示|出现).{0,15}(但|却|结果)',  # 描述游戏中发现问题
    r'(看|发现|遇到).{0,10}(回放|淘汰).{0,15}(显示|出现)',  # 回放相关问题
]

# === 引用消息检测 ===
# 微信导出时，引用消息会显示为 [链接] 但实际是引用其他消息
REFERENCE_INDICATOR = u'[链接]'

def has_reference_message(content):
    """检测消息是否包含引用/回复（显示为[链接]）"""
    return REFERENCE_INDICATOR in content

# === 动态规则加载 ===
def load_learned_rules():
    """加载从 review 中学习到的规则"""
    import json
    rules_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'learned_rules.json')
    if os.path.exists(rules_file):
        try:
            with codecs.open(rules_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        'exclude_words': [],
        'new_problem_words': [],
        'new_feature_words': []
    }

def parse_message_file(filepath):
    """解析 message.txt 文件，返回消息列表"""
    messages = []
    current_msg = None
    current_group = None
    
    with codecs.open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            
            # 检测群聊标题行: 聊天对象: xxx[群聊]
            group_match = re.search(r'聊天对象:\s*(.+?)\s*\[群聊\]', line)
            if not group_match:
                group_match = re.search(u'鑱婂ぉ瀵硅薄:\s*(.+?)\s*\[缇よ亰\]', line)
            if group_match:
                current_group = group_match.group(1).strip()
                continue
            
            # 匹配消息头格式: [2026-03-12 14:30:00] 发送者: 内容
            # 群聊中的消息格式
            header_match = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(.+?):\s+(.*)$', line)
            
            if header_match:
                # 保存上一条消息
                if current_msg:
                    messages.append(current_msg)
                
                timestamp_str = header_match.group(1)
                sender = header_match.group(2).strip()
                content = header_match.group(3)
                
                current_msg = {
                    'timestamp': timestamp_str,
                    'group': current_group,
                    'sender': sender,
                    'content': content
                }
            elif current_msg and line and not line.startswith('='):
                # 消息内容续行
                if current_msg['content']:
                    current_msg['content'] += '\n'
                current_msg['content'] += line
        
        # 保存最后一条消息
        if current_msg:
            messages.append(current_msg)
    
    return messages

def is_bug_report(content, learned_rules=None):
    """
    智能判断消息是否是 bug 反馈
    
    匹配策略:
    0. 检查短消息排除列表
    1. 检查学习到的排除词和模式（优先）
    2. 高优先级关键词直接匹配
    3. 问题词 + 功能词 组合匹配（包括学习到的新词）
    4. Bug 句式模式匹配
    """
    if learned_rules is None:
        learned_rules = load_learned_rules()
    
    content_stripped = content.strip()
    
    # 策略0a: 短消息排除（少于10个字符的简短消息）
    short_excludes = learned_rules.get('short_message_exclude', [])
    if len(content_stripped) < 15:
        for short in short_excludes:
            if short in content_stripped:
                return False
        # 纯叫人的消息
        if content_stripped in ['bug小哥', 'bug小弟', '修bug', '举报了', '没用', '无异常']:
            return False
    
    # 策略0b: 检查排除模式（正则）
    exclude_patterns = learned_rules.get('exclude_patterns', [])
    for pattern in exclude_patterns:
        try:
            if re.search(pattern, content):
                return False
        except:
            pass
    
    # 策略0c: 检查是否命中排除词
    exclude_words = learned_rules.get('exclude_words', [])
    for word in exclude_words:
        if word in content:
            return False
    
    # 策略1: 高优先级关键词直接匹配
    for keyword in BUG_KEYWORDS_HIGH:
        if keyword in content:
            # 排除群公告等非反馈内容
            if u'欢迎' in content and u'反馈' in content:
                continue
            if u'联系' in content and u'处理' in content:
                continue
            return True
    
    # 策略2: 问题词 + 功能词 组合匹配
    # 合并基础词库和学习到的新词
    problem_words = list(BUG_PROBLEM_WORDS) + learned_rules.get('new_problem_words', [])
    feature_words = list(BUG_FEATURE_WORDS) + learned_rules.get('new_feature_words', [])
    
    has_problem = False
    has_feature = False
    
    for word in problem_words:
        if word in content:
            has_problem = True
            break
    
    for word in feature_words:
        if word in content:
            has_feature = True
            break
    
    if has_problem and has_feature:
        # 额外验证: 排除纯提问句（以问号结尾且无具体问题描述）
        if content.strip().endswith(u'?') or content.strip().endswith(u'？'):
            # 如果只是简单提问，不算 bug
            if len(content) < 30 and u'是不是' not in content:
                return False
        return True
    
    # 策略3: Bug 句式模式匹配
    for pattern in BUG_PATTERNS:
        if re.search(pattern, content):
            return True
    
    return False

def filter_messages(messages, group_name, nickname):
    """筛选指定群的 bug 反馈和 @我 的消息"""
    bug_messages = []
    at_me_messages = []
    
    # 构建 @我 的正则模式
    if nickname:
        at_pattern = re.compile(r'@' + re.escape(nickname), re.IGNORECASE)
    else:
        at_pattern = None
    
    for msg in messages:
        # 检查是否匹配群名（部分匹配）
        if msg['group'] is None:
            continue
        if group_name.lower() not in msg['group'].lower():
            continue
        
        content = msg['content']
        is_at_me = False
        
        # 使用智能 bug 检测
        is_bug = is_bug_report(content)
        
        # 检查是否 @我
        if at_pattern and at_pattern.search(content):
            is_at_me = True
        
        if is_bug:
            bug_messages.append(msg)
        if is_at_me:
            at_me_messages.append(msg)
    
    return bug_messages, at_me_messages

def format_message_with_ref_marker(msg, max_length=200):
    """格式化消息内容，如果包含引用消息则添加标记"""
    content = msg['content'][:max_length].replace('\n', ' ')
    if len(msg['content']) > max_length:
        content += u'...'
    
    # 如果包含引用消息，添加标记
    if has_reference_message(msg['content']):
        content += u' ⚠️含引用'
    
    return content

def generate_report(bug_messages, at_me_messages, group_name, output_path):
    """生成分析报告"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 去重统计
    all_msgs = {}
    for m in bug_messages + at_me_messages:
        key = "{0}_{1}_{2}".format(m['timestamp'], m['sender'], m['content'][:50])
        all_msgs[key] = m
    unique_count = len(all_msgs)
    
    # 统计含引用消息的数量
    ref_count = 0
    for m in list(all_msgs.values()):
        if has_reference_message(m['content']):
            ref_count += 1
    
    report_lines = [
        u"📊 微信群 Bug 反馈分析报告",
        u"=" * 40,
        u"群名称: {0}".format(group_name),
        u"分析时间: {0}".format(now),
        u"",
        u"📌 摘要统计",
        u"-" * 40,
        u"Bug 相关消息: {0} 条".format(len(bug_messages)),
        u"@我 的消息: {0} 条".format(len(at_me_messages)),
        u"去重后总计: {0} 条".format(unique_count),
    ]
    
    # 如果有引用消息，添加提示
    if ref_count > 0:
        report_lines.append(u"⚠️ 含引用消息: {0} 条 (需人工查看微信原文)".format(ref_count))
    
    report_lines.append(u"")
    
    # Bug 反馈详情
    if bug_messages:
        report_lines.append(u"🐛 Bug 反馈详情 (按时间排序)")
        report_lines.append(u"-" * 40)
        for msg in sorted(bug_messages, key=lambda x: x['timestamp']):
            content_full = format_message_with_ref_marker(msg, 500)
            report_lines.append(u"[{0}] {1}: {2}".format(msg['timestamp'], msg['sender'], content_full))
        report_lines.append(u"")
    
    # @我 的消息
    if at_me_messages:
        report_lines.append(u"📢 @我 的消息")
        report_lines.append(u"-" * 40)
        for msg in sorted(at_me_messages, key=lambda x: x['timestamp']):
            content_preview = format_message_with_ref_marker(msg, 100)
            report_lines.append(u"[{0}] {1}: {2}".format(msg['timestamp'], msg['sender'], content_preview))
        report_lines.append(u"")
    
    # 如果有引用消息，添加说明
    if ref_count > 0:
        report_lines.append(u"")
        report_lines.append(u"📋 说明:")
        report_lines.append(u"-" * 40)
        report_lines.append(u"⚠️含引用 = 该消息引用/回复了其他消息，")
        report_lines.append(u"   但引用内容无法自动解析，请到微信中查看原文。")
    
    report_content = '\n'.join(report_lines)
    
    # 写入完整报告
    with codecs.open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    # 生成摘要报告（用于 POPO 推送，包含完整内容）
    summary_lines = [
        u"📊 微信群 Bug 反馈分析报告",
        u"群名: {0}".format(group_name),
        u"时间: {0}".format(now),
        u"",
        u"📌 统计:",
        u"• Bug 消息: {0} 条".format(len(bug_messages)),
        u"• @我 消息: {0} 条".format(len(at_me_messages)),
        u"• 去重总计: {0} 条".format(unique_count)
    ]
    
    # 如果有引用消息，添加提示
    if ref_count > 0:
        summary_lines.append(u"• ⚠️含引用: {0} 条 (需查看微信原文)".format(ref_count))
    
    # 添加所有 bug 消息的完整内容
    if bug_messages:
        summary_lines.append(u"")
        summary_lines.append(u"🐛 Bug 反馈详情:")
        for i, msg in enumerate(sorted(bug_messages, key=lambda x: x['timestamp']), 1):
            content_full = format_message_with_ref_marker(msg, 200)
            summary_lines.append(u"")
            summary_lines.append(u"{0}️⃣ [{1}] {2}:".format(i, msg['timestamp'][5:16], msg['sender']))
            summary_lines.append(u"{0}".format(content_full))
    
    # 添加所有 @我 的消息完整内容
    if at_me_messages:
        summary_lines.append(u"")
        summary_lines.append(u"📢 @我 的消息:")
        for i, msg in enumerate(sorted(at_me_messages, key=lambda x: x['timestamp']), 1):
            content_full = format_message_with_ref_marker(msg, 200)
            summary_lines.append(u"")
            summary_lines.append(u"{0}️⃣ [{1}] {2}:".format(i, msg['timestamp'][5:16], msg['sender']))
            summary_lines.append(u"{0}".format(content_full))
    
    summary_content = '\n'.join(summary_lines)
    
    # 写入摘要报告
    summary_path = output_path.replace('.txt', '_summary.txt')
    with codecs.open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary_content)
    
    return report_content, summary_content

def safe_decode(s):
    """安全地将字符串解码为 unicode"""
    if PY2:
        if isinstance(s, str):
            try:
                return s.decode('utf-8')
            except:
                try:
                    return s.decode('gbk')
                except:
                    return s.decode('utf-8', 'ignore')
        return s
    return s

def main():
    parser = argparse.ArgumentParser(description='微信群 Bug 反馈分析器')
    parser.add_argument('--input', '-i', required=True, help='输入的 message.txt 文件路径')
    parser.add_argument('--group', '-g', required=True, help='要分析的群名称（支持部分匹配）')
    parser.add_argument('--nickname', '-n', required=True, help='用户的微信昵称')
    parser.add_argument('--output', '-o', required=True, help='输出报告文件路径')
    
    args = parser.parse_args()
    
    # 解码参数
    group_name = safe_decode(args.group)
    nickname = safe_decode(args.nickname)
    
    # 检查输入文件
    if not os.path.exists(args.input):
        print("[ERROR] Input file not found: {0}".format(args.input))
        return 1
    
    print("[INFO] Reading messages: {0}".format(args.input))
    messages = parse_message_file(args.input)
    print("[INFO] Total messages read: {0}".format(len(messages)))
    
    print("[INFO] Filtering messages for group...")
    bug_messages, at_me_messages = filter_messages(messages, group_name, nickname)
    
    print("[OK] Bug messages found: {0}".format(len(bug_messages)))
    print("[OK] @me messages found: {0}".format(len(at_me_messages)))
    
    print("[INFO] Generating report: {0}".format(args.output))
    report, summary = generate_report(bug_messages, at_me_messages, group_name, args.output)
    
    print("\n" + "=" * 50)
    print("Report Summary:")
    print("=" * 50)
    try:
        print(summary)
    except:
        print("[Note] Summary saved to file (console encoding issue)")
    print("=" * 50)
    
    summary_path = args.output.replace('.txt', '_summary.txt')
    print("\n[OK] Full report: {0}".format(args.output))
    print("[OK] Summary report: {0}".format(summary_path))
    
    return 0

if __name__ == '__main__':
    sys.exit(main())