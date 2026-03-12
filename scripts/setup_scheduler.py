#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
定时任务配置脚本
用于设置 Windows 计划任务，每小时自动运行分析
"""

from __future__ import print_function
from __future__ import unicode_literals
import os
import sys
import subprocess

# Python 2/3 兼容
PY2 = sys.version_info[0] == 2
if PY2:
    reload(sys)
    sys.setdefaultencoding('utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
TASK_NAME = "WechatBugAnalyzer_AutoAnalysis"

def get_python_path():
    """获取 Python 解释器路径"""
    return sys.executable

def create_task():
    """创建 Windows 计划任务"""
    python_path = get_python_path()
    script_path = os.path.join(SCRIPT_DIR, 'auto_analyze.py')
    
    # 创建计划任务命令
    # 每小时运行一次
    cmd = [
        'schtasks', '/create',
        '/tn', TASK_NAME,
        '/tr', '"{0}" "{1}"'.format(python_path, script_path),
        '/sc', 'HOURLY',
        '/mo', '1',
        '/f'  # 强制覆盖已存在的任务
    ]
    
    print("[INFO] Creating scheduled task: {0}".format(TASK_NAME))
    print("[INFO] Command: {0}".format(' '.join(cmd)))
    
    try:
        result = subprocess.call(cmd, shell=True)
        if result == 0:
            print("[OK] Scheduled task created successfully!")
            print("")
            print("📅 任务配置:")
            print("  - 名称: {0}".format(TASK_NAME))
            print("  - 频率: 每小时")
            print("  - 脚本: {0}".format(script_path))
            print("")
            print("💡 提示:")
            print("  - 运行 'schtasks /query /tn {0}' 查看任务状态".format(TASK_NAME))
            print("  - 运行 'schtasks /run /tn {0}' 立即执行".format(TASK_NAME))
            print("  - 运行 'python setup_scheduler.py --disable' 禁用任务")
            return True
        else:
            print("[ERROR] Failed to create scheduled task (code: {0})".format(result))
            return False
    except Exception as e:
        print("[ERROR] Exception: {0}".format(str(e)))
        return False

def delete_task():
    """删除 Windows 计划任务"""
    cmd = ['schtasks', '/delete', '/tn', TASK_NAME, '/f']
    
    print("[INFO] Deleting scheduled task: {0}".format(TASK_NAME))
    
    try:
        result = subprocess.call(cmd, shell=True)
        if result == 0:
            print("[OK] Scheduled task deleted successfully!")
            return True
        else:
            print("[ERROR] Failed to delete scheduled task (code: {0})".format(result))
            return False
    except Exception as e:
        print("[ERROR] Exception: {0}".format(str(e)))
        return False

def query_task():
    """查询计划任务状态"""
    cmd = ['schtasks', '/query', '/tn', TASK_NAME, '/fo', 'LIST']
    
    print("[INFO] Querying scheduled task: {0}".format(TASK_NAME))
    
    try:
        result = subprocess.call(cmd, shell=True)
        return result == 0
    except Exception as e:
        print("[ERROR] Exception: {0}".format(str(e)))
        return False

def run_task():
    """立即运行计划任务"""
    cmd = ['schtasks', '/run', '/tn', TASK_NAME]
    
    print("[INFO] Running scheduled task: {0}".format(TASK_NAME))
    
    try:
        result = subprocess.call(cmd, shell=True)
        if result == 0:
            print("[OK] Task started!")
            return True
        else:
            print("[ERROR] Failed to run task (code: {0})".format(result))
            return False
    except Exception as e:
        print("[ERROR] Exception: {0}".format(str(e)))
        return False

def create_startup_script():
    """创建启动脚本（用于后台运行守护进程）"""
    bat_content = '''@echo off
cd /d "{0}"
start /min "" pythonw "{1}" --daemon
echo Daemon started in background
'''.format(SKILL_DIR, os.path.join(SCRIPT_DIR, 'auto_analyze.py'))
    
    bat_path = os.path.join(SKILL_DIR, 'start_daemon.bat')
    with open(bat_path, 'w') as f:
        f.write(bat_content)
    
    print("[OK] Startup script created: {0}".format(bat_path))
    print("💡 双击此脚本可在后台启动守护进程")
    return bat_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description='定时任务配置')
    parser.add_argument('--enable', action='store_true', help='启用定时任务')
    parser.add_argument('--disable', action='store_true', help='禁用定时任务')
    parser.add_argument('--status', action='store_true', help='查看任务状态')
    parser.add_argument('--run', action='store_true', help='立即运行')
    parser.add_argument('--daemon-script', action='store_true', help='创建守护进程启动脚本')
    
    args = parser.parse_args()
    
    if args.enable:
        create_task()
    elif args.disable:
        delete_task()
    elif args.status:
        query_task()
    elif args.run:
        run_task()
    elif args.daemon_script:
        create_startup_script()
    else:
        parser.print_help()
        print("")
        print("示例:")
        print("  python setup_scheduler.py --enable     # 启用每小时定时任务")
        print("  python setup_scheduler.py --disable    # 禁用定时任务")
        print("  python setup_scheduler.py --status     # 查看任务状态")
        print("  python setup_scheduler.py --run        # 立即运行一次")

if __name__ == '__main__':
    main()