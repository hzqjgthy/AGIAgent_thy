#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (c) 2025 AGI Agent Research Group.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""
任务反思脚本
分析任务日志，使用LLM进行深度反思，生成skill文件
"""

import os
import re
import argparse
import logging
import sys
import yaml
import time
import requests
from string import Template
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# 支持直接以脚本方式运行：
# python src/skill_evolve/task_reflection.py --app xxx
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from src.config_loader import (
    load_config, get_api_key, get_api_base, get_model,
    get_gui_default_data_directory
)
from src.tools.print_system import print_current, print_error, print_system
from src.skill_evolve.skill_tools import SkillTools


class TaskReflection:
    """任务反思处理器"""
    
    def __init__(
        self,
        root_dir: Optional[str] = None,
        config_file: str = "config/config.txt",
        app_name: Optional[str] = None,
    ):
        """
        初始化任务反思处理器
        
        Args:
            root_dir: 根目录（如果指定，覆盖config中的设置）
            config_file: 配置文件路径
            app_name: 应用名（可选）。若对应 app 下存在 skill prompt 文件，则覆盖全局默认文件
        """
        self.config_file = config_file
        self.config = load_config(config_file)
        self.project_root = self._find_project_root()
        self.app_name = app_name.strip() if isinstance(app_name, str) and app_name.strip() else None
        
        # 确定根目录
        if root_dir:
            self.root_dir = os.path.abspath(root_dir)
        else:
            data_dir = get_gui_default_data_directory(config_file)
            if data_dir:
                self.root_dir = data_dir
            else:
                # 默认使用data目录
                self.root_dir = os.path.join(self.project_root, "data") if self.project_root else "data"
        
        # 初始化LLM客户端
        self.api_key = get_api_key(config_file)
        self.api_base = get_api_base(config_file)
        self.model = get_model(config_file)
        
        self.llm_client = None
        self.is_claude = False
        
        if self.api_key and self.model:
            if 'claude' in self.model.lower() or 'anthropic' in str(self.api_base).lower():
                if ANTHROPIC_AVAILABLE:
                    # 对于minimax和GLM等使用Anthropic兼容API的服务，需要传入base_url
                    if 'bigmodel.cn' in str(self.api_base).lower() or 'minimaxi.com' in str(self.api_base).lower():
                        self.llm_client = anthropic.Anthropic(api_key=self.api_key, base_url=self.api_base)
                    else:
                        self.llm_client = anthropic.Anthropic(api_key=self.api_key)
                    self.is_claude = True
            else:
                if OPENAI_AVAILABLE:
                    self.llm_client = OpenAI(api_key=self.api_key, base_url=self.api_base)
        
        # 初始化skill工具
        self.skill_tools = SkillTools(workspace_root=self.root_dir)
        
        # 设置日志
        self.logger = self._setup_logger()
        self.reflection_prompts = self._load_reflection_prompts()
    
    def _find_project_root(self) -> Optional[str]:
        """查找项目根目录"""
        current = Path(__file__).resolve()
        for _ in range(10):
            config_dir = current / "config"
            if config_dir.exists() and config_dir.is_dir():
                return str(current)
            if current == current.parent:
                break
            current = current.parent
        return None
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('task_reflection')
        logger.setLevel(logging.INFO)
        
        # 创建日志目录
        if self.skill_tools.experience_dir:
            log_dir = os.path.join(self.skill_tools.experience_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            # 日志文件
            log_file = os.path.join(log_dir, f"task_reflection_{datetime.now().strftime('%Y%m%d')}.log")
            
            # 文件处理器
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # 格式
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
        
        return logger

    def _get_reflection_prompt_file_path(self) -> str:
        """获取skill反思prompt配置文件路径，优先使用 app 覆盖文件。"""
        if self.project_root and self.app_name:
            app_dir = os.path.join(self.project_root, 'apps', self.app_name)
            if not os.path.isdir(app_dir):
                raise FileNotFoundError(
                    f"App directory not found: {app_dir}. "
                    f"Cannot use --app {self.app_name} for skill reflection prompt override."
                )

            app_prompt_path = os.path.join(
                app_dir,
                'prompts',
                'skill_reflection_prompts.yaml',
            )
            if os.path.exists(app_prompt_path):
                return app_prompt_path

        if self.project_root:
            return os.path.join(self.project_root, 'prompts', 'skill_reflection_prompts.yaml')
        return os.path.join('prompts', 'skill_reflection_prompts.yaml')

    def _load_reflection_prompts(self) -> Dict[str, str]:
        """从统一配置文件加载skill反思prompt，缺失文件或关键字段时直接报错。"""
        prompt_file_path = self._get_reflection_prompt_file_path()

        if not os.path.exists(prompt_file_path):
            raise FileNotFoundError(
                f"Skill reflection prompt file not found: {prompt_file_path}. "
                "Please create prompts/skill_reflection_prompts.yaml with "
                "'default_system_prompt' and 'user_prompt_template'."
            )

        try:
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in skill reflection prompt file {prompt_file_path}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to read skill reflection prompt file {prompt_file_path}: {e}") from e

        if not isinstance(loaded_config, dict):
            raise ValueError(
                f"Invalid prompt config format in {prompt_file_path}: expected a YAML mapping/object."
            )

        required_keys = ('default_system_prompt', 'user_prompt_template')
        prompt_config: Dict[str, str] = {}
        missing_keys = []

        for key in required_keys:
            loaded_value = loaded_config.get(key)
            if isinstance(loaded_value, str) and loaded_value.strip():
                prompt_config[key] = loaded_value.strip()
            else:
                missing_keys.append(key)

        if missing_keys:
            raise ValueError(
                f"Missing or empty required prompt keys in {prompt_file_path}: {', '.join(missing_keys)}"
            )

        return prompt_config

    def _build_reflection_user_prompt(self, task_info: Dict[str, Any], manager_log_content: str) -> str:
        """使用外置模板渲染反思阶段的user prompt。"""
        template = Template(self.reflection_prompts['user_prompt_template'])
        jericho_score_text = ''
        if self._is_jericho_task(task_info):
            score_snapshot = self._extract_jericho_score_snapshot(manager_log_content)
            jericho_score_text = self._format_jericho_score_snapshot(score_snapshot)

        prompt_values = {
            'output_dir': str(task_info.get('output_dir', '')),
            'user_requirements': str(task_info.get('user_requirements', [])),
            'tool_call_count': str(len(task_info.get('tool_calls', []))),
            'error_count': str(len(task_info.get('errors', []))),
            'task_completed_text': '是' if task_info.get('task_completed') else '否',
            'user_interruptions_count': str(len(task_info.get('user_interruptions', []))),
            'log_summary': str(task_info.get('log_summary', '')),
            'jericho_score_text': jericho_score_text,
            'manager_log_content': manager_log_content if manager_log_content else '日志内容为空',
        }
        return template.safe_substitute(prompt_values)

    def _is_jericho_task(self, task_info: Dict[str, Any]) -> bool:
        """判断当前任务是否为 Jericho 数据集任务。"""
        output_dir = str(task_info.get('output_dir', '')).lower()
        if 'tale_jericho' in output_dir or 'jerichoenv' in output_dir:
            return True

        user_reqs = ' '.join(task_info.get('user_requirements', [])).lower()
        if 'jericho' in user_reqs:
            return True

        log_content = str(task_info.get('log_content', '')).lower()
        if 'dataset: jericho' in log_content or 'tale_jericho_action' in log_content:
            return True

        return False

    def _extract_jericho_score_snapshot(self, log_content: str) -> Dict[str, Any]:
        """从日志中提取 Jericho 任务的最终分数快照与状态快照。"""
        def _last_float(metric_name: str) -> Optional[float]:
            pattern = rf"{metric_name}\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)"
            matches = re.findall(pattern, log_content, re.IGNORECASE)
            if not matches:
                return None
            try:
                return float(matches[-1])
            except ValueError:
                return None

        def _last_bool(metric_name: str) -> Optional[bool]:
            pattern = rf"{metric_name}\s*[:=]\s*(true|false)"
            matches = re.findall(pattern, log_content, re.IGNORECASE)
            if not matches:
                return None
            return matches[-1].lower() == 'true'

        def _last_str(metric_name: str) -> Optional[str]:
            pattern = rf"{metric_name}\s*[:=]\s*([A-Za-z0-9_\\.-]+)"
            matches = re.findall(pattern, log_content, re.IGNORECASE)
            return matches[-1] if matches else None

        return {
            'env_name': _last_str('env_name'),
            'best_score': _last_float('best_score'),
            'current_score': _last_float('current_score'),
            'full_score': _last_float('full_score'),
            'score_rate': _last_float('score_rate'),
            'moves': _last_float('moves'),
            'done': _last_bool('done'),
            'won': _last_bool('won'),
            'lost': _last_bool('lost'),
        }

    def _format_jericho_score_snapshot(self, snapshot: Dict[str, Any]) -> str:
        """格式化 Jericho 分数快照，便于注入到 prompt。"""
        def _fmt(name: str) -> str:
            value = snapshot.get(name)
            return 'N/A' if value is None else str(value)

        return (
            "Jericho关键指标（从manager.out提取，优先按最后一次记录判断）:\n"
            f"- env_name: {_fmt('env_name')}\n"
            f"- best_score: {_fmt('best_score')}\n"
            f"- current_score: {_fmt('current_score')}\n"
            f"- full_score: {_fmt('full_score')}\n"
            f"- score_rate: {_fmt('score_rate')}\n"
            f"- moves: {_fmt('moves')}\n"
            f"- done: {_fmt('done')}\n"
            f"- won: {_fmt('won')}\n"
            f"- lost: {_fmt('lost')}\n"
        )
    
    def _find_all_output_dirs(self) -> List[Tuple[str, float]]:
        """
        查找所有output_XXX目录
        
        查找范围（按优先级）：
        1. data/output_XXX/ (直接在data目录下，由agia.py生成)
        2. data/{user_dir}/output_XXX/ (标准结构)
        3. data/benchmark_results/*/baseline_outputs/output_XXX/ (评测结构)
        4. data/benchmark_results/*/skill_outputs/output_XXX/ (评测结构)
        
        Returns:
            [(目录路径, 修改时间), ...] 列表，按时间倒序
        """
        output_dirs = []
        
        if not os.path.exists(self.root_dir):
            self.logger.warning(f"Root directory not found: {self.root_dir}")
            return output_dirs
        
        # 方法0: 直接在data目录下查找 output_XXX（由agia.py生成的结构）
        for item in os.listdir(self.root_dir):
            item_path = os.path.join(self.root_dir, item)
            if os.path.isdir(item_path) and item.startswith('output_'):
                # 检查是否是有效的output目录（包含workspace或logs目录）
                workspace_dir = os.path.join(item_path, "workspace")
                logs_dir = os.path.join(item_path, "logs")
                if os.path.exists(workspace_dir) or os.path.exists(logs_dir):
                    try:
                        mtime = os.path.getmtime(item_path)
                        output_dirs.append((item_path, mtime))
                    except OSError:
                        continue
        
        # 方法1: 遍历所有用户目录，查找标准结构 data/{user_dir}/output_XXX/
        for item in os.listdir(self.root_dir):
            item_path = os.path.join(self.root_dir, item)
            if not os.path.isdir(item_path) or item.startswith('.') or item.startswith('output_'):
                continue
            
            # 在用户目录下查找output_XXX
            try:
                for subitem in os.listdir(item_path):
                    subitem_path = os.path.join(item_path, subitem)
                    if os.path.isdir(subitem_path) and subitem.startswith('output_'):
                        mtime = os.path.getmtime(subitem_path)
                        output_dirs.append((subitem_path, mtime))
            except (OSError, PermissionError):
                continue
        
        # 方法2: 查找评测结构 data/benchmark_results/*/baseline_outputs/output_XXX/
        benchmark_results_dir = os.path.join(self.root_dir, "benchmark_results")
        if os.path.exists(benchmark_results_dir):
            try:
                for benchmark_dir in os.listdir(benchmark_results_dir):
                    benchmark_path = os.path.join(benchmark_results_dir, benchmark_dir)
                    if not os.path.isdir(benchmark_path):
                        continue
                    
                    # 查找 baseline_outputs 和 skill_outputs 目录
                    for output_type in ["baseline_outputs", "skill_outputs"]:
                        outputs_dir = os.path.join(benchmark_path, output_type)
                        if os.path.exists(outputs_dir):
                            try:
                                for output_item in os.listdir(outputs_dir):
                                    output_item_path = os.path.join(outputs_dir, output_item)
                                    if os.path.isdir(output_item_path) and output_item.startswith('output_'):
                                        mtime = os.path.getmtime(output_item_path)
                                        output_dirs.append((output_item_path, mtime))
                            except (OSError, PermissionError):
                                continue
            except (OSError, PermissionError):
                pass
        
        # 去除重复（基于路径）
        seen_paths = set()
        unique_output_dirs = []
        for output_dir, mtime in output_dirs:
            if output_dir not in seen_paths:
                seen_paths.add(output_dir)
                unique_output_dirs.append((output_dir, mtime))
        
        # 按修改时间倒序排序
        unique_output_dirs.sort(key=lambda x: x[1], reverse=True)
        return unique_output_dirs
    
    def _parse_log_file(self, log_file_path: str) -> Dict[str, Any]:
        """
        解析日志文件
        
        Args:
            log_file_path: 日志文件路径
            
        Returns:
            解析结果字典
        """
        result = {
            'user_requirements': [],
            'tool_calls': [],
            'errors': [],
            'task_completed': False,
            'user_interruptions': [],
            'agent_messages': [],
            'log_content': ''  # 保存完整日志内容
        }
        
        if not os.path.exists(log_file_path):
            return result
        
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 保存日志内容（如果太长则截取关键部分）
            # 提高阈值到50000，确保能包含更多上下文
            if len(content) > 50000:
                # 如果日志太长，保留开头、失败点和成功点附近的内容
                lines = content.split('\n')
                # 保留前2000行（增加开头保留量）
                start_lines = lines[:2000]
                
                # 查找关键信息位置
                # 1. 游戏类型和规则相关的行（棋盘大小、游戏规则等）
                game_info_indices = []
                for i, line in enumerate(lines):
                    if any(keyword in line for keyword in ['12x12', '棋盘', '五子棋', 'Gomoku', '连成', '获胜', '规则', 'game']):
                        game_info_indices.append(i)
                
                # 2. 失败点
                failure_indices = [i for i, line in enumerate(lines) if '游戏结束' in line and '环境获胜' in line or '❌' in line]
                
                # 3. 成功点
                success_indices = [i for i, line in enumerate(lines) if ('获胜' in line and '大模型获胜' in line) or '🎉' in line or 'TASK_COMPLETED' in line]
                
                # 收集关键区域
                key_lines = []
                seen_indices = set()
                
                # 收集游戏信息相关行（前后各50行）
                for idx in game_info_indices[:5]:  # 前5个游戏信息点
                    for i in range(max(0, idx-50), min(len(lines), idx+50)):
                        if i not in seen_indices:
                            key_lines.append(lines[i])
                            seen_indices.add(i)
                
                # 收集失败点前后各150行（增加上下文）
                for idx in failure_indices[:5]:  # 最多5个失败点
                    for i in range(max(0, idx-150), min(len(lines), idx+150)):
                        if i not in seen_indices:
                            key_lines.append(lines[i])
                            seen_indices.add(i)
                
                # 收集成功点前后各200行（完整保留成功过程）
                for idx in success_indices:
                    for i in range(max(0, idx-200), min(len(lines), idx+200)):
                        if i not in seen_indices:
                            key_lines.append(lines[i])
                            seen_indices.add(i)
                
                # 按行号排序，保持时间顺序
                key_lines_with_idx = [(i, lines[i]) for i in seen_indices if i >= 2000]  # 排除已包含在start_lines中的行
                key_lines_with_idx.sort()
                key_lines_ordered = [line for _, line in key_lines_with_idx]
                
                # 合并内容
                result['log_content'] = '\n'.join(start_lines) + '\n... [中间部分已省略，仅保留关键信息] ...\n' + '\n'.join(key_lines_ordered)
                self.logger.info(f"Log content truncated from {len(content)} to {len(result['log_content'])} characters")
            else:
                result['log_content'] = content
                self.logger.info(f"Log content preserved in full: {len(content)} characters")
            
            # 提取用户需求
            user_req_pattern = r'Received user requirement[:\s]+(.+?)(?:\n|$)'
            for match in re.finditer(user_req_pattern, content, re.MULTILINE | re.IGNORECASE):
                result['user_requirements'].append(match.group(1).strip())
            
            # 提取工具调用（XML格式）
            tool_call_pattern = r'<invoke[^>]*>(.*?)</invoke>'
            for match in re.finditer(tool_call_pattern, content, re.DOTALL):
                result['tool_calls'].append(match.group(0))
            
            # 提取错误反馈
            error_pattern = r'ERROR FEEDBACK[:\s]+(.+?)(?:\n|$)'
            for match in re.finditer(error_pattern, content, re.MULTILINE | re.IGNORECASE):
                result['errors'].append(match.group(1).strip())
            
            # 检查TASK_COMPLETED
            if 'TASK_COMPLETED' in content or 'TASK COMPLETED' in content:
                result['task_completed'] = True
            
            # 检测用户中断点
            # user requirement之前200个字符内没有TASK_COMPLETED（第一行除外）
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'Received user requirement' in line or 'user requirement' in line.lower():
                    if i == 0:
                        continue
                    
                    # 检查前200个字符
                    prev_text = '\n'.join(lines[max(0, i-10):i])
                    if len(prev_text) > 200:
                        prev_text = prev_text[-200:]
                    
                    if 'TASK_COMPLETED' not in prev_text and 'TASK COMPLETED' not in prev_text:
                        result['user_interruptions'].append({
                            'line': i,
                            'requirement': line.strip()
                        })
            
            # 提取agent消息（如果是agent日志）
            if 'agent_' in os.path.basename(log_file_path):
                agent_msg_pattern = r'Agent\s+\d+.*?:(.+?)(?:\n|$)'
                for match in re.finditer(agent_msg_pattern, content, re.MULTILINE | re.IGNORECASE):
                    result['agent_messages'].append(match.group(1).strip())
        
        except Exception as e:
            self.logger.error(f"Error parsing log file {log_file_path}: {e}")
        
        return result
    
    def _call_llm_reflection(self, task_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用LLM进行深度反思
        
        Args:
            task_info: 任务信息字典
            
        Returns:
            LLM反思结果，包含反思内容和需要备份的文件列表
        """
        if not self.llm_client:
            return {
                'reflection': 'LLM client not available',
                'files_to_backup': [],
                'usage_conditions': None
            }
        
        system_prompt = self.reflection_prompts['default_system_prompt']

        # 获取manager.out的详细内容
        manager_log_content = task_info.get('log_content', '')
        
        # 记录日志内容长度，用于调试
        self.logger.info(f"Manager.out content length: {len(manager_log_content)} characters")
        
        # 如果内容为空，记录警告
        if not manager_log_content:
            self.logger.warning("Manager.out content is empty! LLM will not see detailed execution history.")
        
        user_prompt = self._build_reflection_user_prompt(task_info, manager_log_content)
        
        # 记录实际传递给LLM的prompt长度
        self.logger.info(f"User prompt length: {len(user_prompt)} characters")
        
        try:
            if self.is_claude:
                # 使用Anthropic客户端（支持标准Anthropic API和兼容API如minimax、GLM）
                response = self.llm_client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.7
                )
                # 正确处理不同类型的content block（text和thinking）
                reflection_text = ""
                for content_block in response.content:
                    if hasattr(content_block, 'type'):
                        if content_block.type == "text":
                            reflection_text += getattr(content_block, 'text', '')
                        elif content_block.type == "thinking":
                            # thinking block可能有text或thinking属性
                            thinking_text = getattr(content_block, 'text', None) or getattr(content_block, 'thinking', None)
                            if thinking_text:
                                reflection_text += thinking_text
                    else:
                        # 兼容旧版本，直接尝试text属性
                        reflection_text += getattr(content_block, 'text', '')
            else:
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=4000,
                    temperature=0.7
                )
                reflection_text = response.choices[0].message.content if response.choices else ""
            
            # 解析文件列表和使用条件
            files_to_backup = []
            usage_conditions = None
            
            # 提取FILES_TO_BACKUP（应该在USAGE_CONDITIONS之前）
            if 'FILES_TO_BACKUP:' in reflection_text:
                files_section = reflection_text.split('FILES_TO_BACKUP:')[1].strip()
                # 如果USAGE_CONDITIONS在FILES_TO_BACKUP之后，需要排除它
                if 'USAGE_CONDITIONS:' in files_section:
                    files_section = files_section.split('USAGE_CONDITIONS:')[0].strip()
                for line in files_section.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('USAGE_CONDITIONS:'):
                        files_to_backup.append(line)
            
            # 提取USAGE_CONDITIONS
            if 'USAGE_CONDITIONS:' in reflection_text:
                usage_section = reflection_text.split('USAGE_CONDITIONS:')[1].strip()
                # 提取第一行作为usage conditions（去除可能的额外内容）
                usage_conditions = usage_section.split('\n')[0].strip()
                # 如果还有FILES_TO_BACKUP在后面，需要排除
                if 'FILES_TO_BACKUP:' in usage_conditions:
                    usage_conditions = usage_conditions.split('FILES_TO_BACKUP:')[0].strip()
            
            # 移除文件列表和使用条件部分，获取纯反思内容
            reflection = reflection_text
            if 'FILES_TO_BACKUP:' in reflection:
                reflection = reflection.split('FILES_TO_BACKUP:')[0].strip()
            if 'USAGE_CONDITIONS:' in reflection:
                reflection = reflection.split('USAGE_CONDITIONS:')[0].strip()
            
            return {
                'reflection': reflection,
                'files_to_backup': files_to_backup,
                'usage_conditions': usage_conditions
            }
        
        except Exception as e:
            self.logger.error(f"Error calling LLM: {e}")
            return {
                'reflection': f'Error in LLM call: {str(e)}',
                'files_to_backup': [],
                'usage_conditions': None
            }
    
    def _backup_files(self, output_dir: str, files_to_backup: List[str], skill_id: str) -> List[str]:
        """
        备份文件到skill代码目录
        
        Args:
            output_dir: 任务输出目录
            files_to_backup: 要备份的文件路径列表（相对于workspace）
            skill_id: skill ID
            
        Returns:
            成功备份的文件列表
        """
        workspace_dir = os.path.join(output_dir, "workspace")
        if not os.path.exists(workspace_dir):
            return []
        
        copied_files = []
        
        for file_path in files_to_backup:
            try:
                # 构建完整路径
                if os.path.isabs(file_path):
                    src_path = file_path
                else:
                    src_path = os.path.join(workspace_dir, file_path)
                
                if not os.path.exists(src_path):
                    continue
                
                # 只备份代码文件和文档文件
                ext = os.path.splitext(src_path)[1].lower()
                code_exts = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp', '.go', '.rs', '.rb', '.php'}
                doc_exts = {'.md', '.txt', '.rst'}
                
                if ext not in code_exts and ext not in doc_exts:
                    continue
                
                # 使用copy_skill_files工具备份
                rel_path = os.path.relpath(src_path, workspace_dir)
                result = self.skill_tools.copy_skill_files(skill_id, [rel_path])
                if result.get('status') == 'success':
                    copied_files.extend(result.get('copied_files', []))
            
            except Exception as e:
                self.logger.error(f"Error backing up file {file_path}: {e}")
        
        return copied_files
    
    def _generate_skill(self, task_info: Dict[str, Any], reflection_result: Dict[str, Any]) -> Optional[str]:
        """
        生成skill文件
        
        Args:
            task_info: 任务信息
            reflection_result: 反思结果
            
        Returns:
            生成的skill文件路径
        """
        if not self.skill_tools.experience_dir:
            return None
        
        try:
            # 生成skill_id（使用时间戳）
            skill_id = str(int(time.time()))
            
            # 从反思内容中提取标题（使用第一行或前50个字符）
            reflection = reflection_result.get('reflection', '')
            title = reflection.split('\n')[0][:50] if reflection else f"Task from {task_info['output_dir']}"
            if not title:
                title = f"Task from {os.path.basename(task_info['output_dir'])}"
            
            # 生成文件名
            safe_title = self.skill_tools._sanitize_filename(title)
            skill_filename = f"skill_{safe_title}.md"
            skill_file_path = os.path.join(self.skill_tools.experience_dir, skill_filename)
            
            # 如果文件已存在，添加时间戳
            if os.path.exists(skill_file_path):
                name, ext = os.path.splitext(skill_filename)
                skill_filename = f"{name}_{skill_id}{ext}"
                skill_file_path = os.path.join(self.skill_tools.experience_dir, skill_filename)
            
            # 构建front matter
            user_requirements = task_info.get('user_requirements', [])
            # 优先使用LLM生成的usage_conditions，否则使用user_requirements
            usage_conditions_from_llm = reflection_result.get('usage_conditions')
            if usage_conditions_from_llm:
                usage_conditions_text = usage_conditions_from_llm
            else:
                usage_conditions_text = user_requirements[0][:100] if user_requirements and user_requirements[0] else "通用任务"
                # 如果使用user_requirements，加上前缀
                if usage_conditions_text and not usage_conditions_text.startswith("当"):
                    usage_conditions_text = f"当需要完成类似任务时使用：{usage_conditions_text}"
            
            front_matter = {
                'skill_id': skill_id,
                'title': title,
                'usage_conditions': usage_conditions_text,
                'quality_index': 0.5,
                'fetch_count': 0,
                'related_code': '',
                'task_directories': [os.path.basename(task_info['output_dir'])],
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'last_used_at': None,
                'user_preferences': ''
            }
            
            # 提取用户偏好（从反思内容中）
            if '用户偏好' in reflection or 'user preference' in reflection.lower():
                # 简单提取，可以后续改进
                front_matter['user_preferences'] = "从反思中提取的用户偏好信息"
            
            # 保存skill文件
            self.skill_tools._save_skill_file(skill_file_path, front_matter, reflection)
            
            # 备份文件
            files_to_backup = reflection_result.get('files_to_backup', [])
            if files_to_backup:
                copied_files = self._backup_files(task_info['output_dir'], files_to_backup, skill_id)
                if copied_files:
                    # 更新related_code
                    front_matter['related_code'] = ', '.join(copied_files)
                    self.skill_tools._save_skill_file(skill_file_path, front_matter, reflection)
            
            return skill_file_path
        
        except Exception as e:
            self.logger.error(f"Error generating skill: {e}")
            return None
    
    def process_task(self, output_dir: str) -> bool:
        """
        处理单个任务
        
        Args:
            output_dir: 任务输出目录
            
        Returns:
            是否成功处理
        """
        try:
            self.logger.info(f"Processing task: {output_dir}")
            print_current(f"Processing: {output_dir}")
            
            # 解析日志文件
            logs_dir = os.path.join(output_dir, "logs")
            if not os.path.exists(logs_dir):
                self.logger.warning(f"Logs directory not found: {logs_dir}")
                return False
            
            # 解析manager.out（保留完整内容用于LLM反思）
            manager_log = os.path.join(logs_dir, "manager.out")
            task_info = self._parse_log_file(manager_log)
            task_info['output_dir'] = output_dir
            
            # 解析agent日志
            for filename in os.listdir(logs_dir):
                if filename.startswith('agent_') and filename.endswith('.out'):
                    agent_log = os.path.join(logs_dir, filename)
                    agent_info = self._parse_log_file(agent_log)
                    task_info['agent_messages'].extend(agent_info.get('agent_messages', []))
                    # 如果agent日志有内容，也合并到log_content中（仅保留关键部分）
                    if agent_info.get('log_content') and len(agent_info.get('log_content', '')) < 5000:
                        if task_info.get('log_content'):
                            task_info['log_content'] += f"\n\n--- Agent日志 ({filename}) ---\n{agent_info['log_content']}"
                        else:
                            task_info['log_content'] = agent_info['log_content']
            
            # 生成日志摘要
            log_summary = f"""
工具调用: {len(task_info.get('tool_calls', []))}次
错误: {len(task_info.get('errors', []))}个
用户中断: {len(task_info.get('user_interruptions', []))}次
任务完成: {'是' if task_info.get('task_completed') else '否'}
"""
            task_info['log_summary'] = log_summary
            
            # LLM反思
            reflection_result = self._call_llm_reflection(task_info)
            
            # 生成skill文件
            skill_file = self._generate_skill(task_info, reflection_result)
            
            if skill_file:
                self.logger.info(f"Skill file generated: {skill_file}")
                print_current(f"✅ Skill generated: {skill_file}")
                return True
            else:
                self.logger.error("Failed to generate skill file")
                return False
        
        except Exception as e:
            self.logger.error(f"Error processing task {output_dir}: {e}", exc_info=True)
            return False
    
    def run(self):
        """运行任务反思流程"""
        self.logger.info(f"Starting task reflection process. Root directory: {self.root_dir}")
        print_system(f"Starting task reflection. Root directory: {self.root_dir}")
        
        # 查找所有output目录
        output_dirs = self._find_all_output_dirs()
        
        if not output_dirs:
            self.logger.warning("No output directories found")
            print_current("No output directories found")
            return
        
        self.logger.info(f"Found {len(output_dirs)} output directories")
        print_current(f"Found {len(output_dirs)} tasks to process")
        
        # 处理每个任务
        success_count = 0
        for i, (output_dir, mtime) in enumerate(output_dirs, 1):
            print_current(f"[{i}/{len(output_dirs)}] Processing {os.path.basename(output_dir)}...")
            if self.process_task(output_dir):
                success_count += 1
        
        self.logger.info(f"Task reflection completed. Processed {success_count}/{len(output_dirs)} tasks successfully")
        print_system(f"✅ Task reflection completed. Processed {success_count}/{len(output_dirs)} tasks successfully")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Task reflection script for skill generation')
    parser.add_argument('--root-dir', type=str, help='Root directory for data (overrides config)')
    parser.add_argument('--config', type=str, default='config/config.txt', help='Config file path')
    parser.add_argument(
        '--app',
        type=str,
        default=None,
        help='App name. If apps/{app}/prompts/skill_reflection_prompts.yaml exists, it overrides prompts/skill_reflection_prompts.yaml'
    )
    
    args = parser.parse_args()
    
    reflection = TaskReflection(
        root_dir=args.root_dir,
        config_file=args.config,
        app_name=args.app,
    )
    reflection.run()


if __name__ == '__main__':
    main()
