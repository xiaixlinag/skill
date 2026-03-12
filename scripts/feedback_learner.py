#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
反馈学习系统
通过运营 Review 结果持续迭代识别规则
"""

from __future__ import print_function
from __future__ import unicode_literals
import json
import os
import codecs
import re
from datetime import datetime
from collections import Counter

# Python 2/3 兼容
import sys
PY2 = sys.version_info[0] == 2
if PY2:
    reload(sys)
    sys.setdefaultencoding('utf-8')

# 配置文件路径
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW_HISTORY_FILE = os.path.join(SKILL_DIR, 'review_history.json')
LEARNED_RULES_FILE = os.path.join(SKILL_DIR, 'learned_rules.json')

def load_json(filepath, default=None):
    """加载 JSON 文件"""
    if default is None:
        default = {}
    if not os.path.exists(filepath):
        return default
    try:
        with codecs.open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default

def save_json(filepath, data):
    """保存 JSON 文件"""
    with codecs.open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def safe_str(s):
    """确保字符串是 unicode"""
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

def add_review(message_content, review_type, reason=''):
    """
    添加一条 review 记录
    
    Args:
        message_content: 消息内容
        review_type: 'correct' | 'false_positive' | 'false_negative'
        reason: 标注原因/备注
    """
    history = load_json(REVIEW_HISTORY_FILE, {'reviews': [], 'stats': {}})
    
    # 确保 unicode
    message_content = safe_str(message_content)
    reason = safe_str(reason)
    
    review = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'content': message_content[:200],  # 只保存前200字符
        'type': review_type,
        'reason': reason
    }
    
    history['reviews'].append(review)
    
    # 更新统计
    if 'stats' not in history:
        history['stats'] = {}
    history['stats'][review_type] = history['stats'].get(review_type, 0) + 1
    history['stats']['total'] = history['stats'].get('total', 0) + 1
    
    save_json(REVIEW_HISTORY_FILE, history)
    return review

def extract_keywords(text):
    """从文本中提取关键词（2-4字的词组）"""
    # 简单的中文分词：提取连续的中文字符
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]{2,6}')
    words = chinese_pattern.findall(text)
    return words

def learn_from_reviews():
    """
    从 review 历史中学习，生成/更新规则
    
    学习策略：
    1. 从误报(false_positive)中提取排除词
    2. 从漏报(false_negative)中提取新的问题关键词
    3. 统计高频模式
    """
    history = load_json(REVIEW_HISTORY_FILE, {'reviews': []})
    reviews = history.get('reviews', [])
    
    if not reviews:
        return {'status': 'no_reviews', 'message': '没有 review 数据'}
    
    # 分类 reviews
    false_positives = [r for r in reviews if r['type'] == 'false_positive']
    false_negatives = [r for r in reviews if r['type'] == 'false_negative']
    correct = [r for r in reviews if r['type'] == 'correct']
    
    # 从误报中学习排除词
    exclude_words = Counter()
    for fp in false_positives:
        words = extract_keywords(fp['content'])
        exclude_words.update(words)
    
    # 从漏报中学习新关键词
    new_keywords = Counter()
    for fn in false_negatives:
        words = extract_keywords(fn['content'])
        new_keywords.update(words)
    
    # 从正确识别中确认有效关键词
    confirmed_keywords = Counter()
    for c in correct:
        words = extract_keywords(c['content'])
        confirmed_keywords.update(words)
    
    # 生成学习结果
    learned = load_json(LEARNED_RULES_FILE, {
        'exclude_patterns': [],
        'new_problem_words': [],
        'new_feature_words': [],
        'exclude_words': [],
        'confirmed_patterns': [],
        'learning_count': 0
    })
    
    # 从误报中提取排除模式
    # 策略1: 高频误报词（出现2次以上）直接加入排除列表
    # 策略2: 单次出现但特征明显的词（如 "欢迎"、"黑产" 等）也考虑加入
    for word, count in exclude_words.most_common(30):
        if word in learned['exclude_words']:
            continue
        # 已在正确识别中确认的词不排除
        if word in confirmed_keywords and confirmed_keywords[word] >= count:
            continue
        # 高频词直接加入
        if count >= 2:
            learned['exclude_words'].append(word)
        # 单次出现但明显是非bug特征的词
        elif count == 1 and len(word) >= 2:
            # 检查是否为典型非bug特征词
            non_bug_features = [u'欢迎', u'黑产', u'外挂', u'沉默', u'难道', u'专属']
            if any(feat in word for feat in non_bug_features):
                learned['exclude_words'].append(word)
    
    # 高频漏报词加入新关键词
    for word, count in new_keywords.most_common(20):
        if count >= 1:
            if word not in learned['new_problem_words'] and word not in learned['new_feature_words']:
                # 根据词性判断是问题词还是功能词
                if any(c in word for c in ['不', '没', '错', '失', '坏', '卡', '慢']):
                    learned['new_problem_words'].append(word)
                else:
                    learned['new_feature_words'].append(word)
    
    learned['learning_count'] += 1
    learned['last_learned'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    learned['stats'] = {
        'total_reviews': len(reviews),
        'false_positives': len(false_positives),
        'false_negatives': len(false_negatives),
        'correct': len(correct),
        'accuracy': round(float(len(correct)) / float(len(reviews)) * 100.0, 1) if reviews else 0
    }
    
    save_json(LEARNED_RULES_FILE, learned)
    
    return {
        'status': 'success',
        'stats': learned['stats'],
        'new_exclude_words': learned['exclude_words'][-5:],
        'new_problem_words': learned['new_problem_words'][-5:],
        'new_feature_words': learned['new_feature_words'][-5:]
    }

def get_learned_rules():
    """获取已学习的规则"""
    return load_json(LEARNED_RULES_FILE, {
        'exclude_patterns': [],
        'new_problem_words': [],
        'new_feature_words': [],
        'exclude_words': [],
        'learning_count': 0
    })

def get_review_stats():
    """获取 review 统计信息"""
    history = load_json(REVIEW_HISTORY_FILE, {'reviews': [], 'stats': {}})
    learned = load_json(LEARNED_RULES_FILE, {'learning_count': 0, 'stats': {}})
    
    return {
        'total_reviews': len(history.get('reviews', [])),
        'stats': history.get('stats', {}),
        'learning_count': learned.get('learning_count', 0),
        'accuracy': learned.get('stats', {}).get('accuracy', 'N/A')
    }

def print_review_summary():
    """打印 review 摘要"""
    stats = get_review_stats()
    learned = get_learned_rules()
    
    print("\n" + "=" * 50)
    print("📊 Review 统计摘要")
    print("=" * 50)
    print("总 Review 数: {0}".format(stats['total_reviews']))
    print("学习迭代次数: {0}".format(stats['learning_count']))
    print("当前准确率: {0}%".format(stats['accuracy']))
    print("")
    print("📋 已学习的规则:")
    print("  - 排除词: {0} 个".format(len(learned.get('exclude_words', []))))
    print("  - 新问题词: {0} 个".format(len(learned.get('new_problem_words', []))))
    print("  - 新功能词: {0} 个".format(len(learned.get('new_feature_words', []))))
    print("=" * 50)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='反馈学习系统')
    parser.add_argument('--action', choices=['add', 'learn', 'stats', 'rules'], required=True)
    parser.add_argument('--type', choices=['correct', 'false_positive', 'false_negative'])
    parser.add_argument('--content', help='消息内容')
    parser.add_argument('--reason', default='', help='标注原因')
    
    args = parser.parse_args()
    
    if args.action == 'add':
        if not args.type or not args.content:
            print("ERROR: --type and --content required for add action")
            sys.exit(1)
        result = add_review(args.content, args.type, args.reason)
        print("Review added: {0}".format(result['type']))
    
    elif args.action == 'learn':
        result = learn_from_reviews()
        print("Learning result: {0}".format(json.dumps(result, ensure_ascii=False, indent=2)))
    
    elif args.action == 'stats':
        print_review_summary()
    
    elif args.action == 'rules':
        rules = get_learned_rules()
        print(json.dumps(rules, ensure_ascii=False, indent=2))