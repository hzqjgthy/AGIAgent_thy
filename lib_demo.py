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

AGI Agent Python Library Usage Examples

This file demonstrates how to use AGI Agent as a Python library instead of 
command-line tool. The library provides an OpenAI-like chat interface.
"""

# Import the AGI Agent client
from src.main import AGIAgentClient, create_client

def example_basic_usage():
    """Basic usage example"""
    print("=== Basic Usage Example ===")
    
    # Initialize the client (will automatically read from config/config.txt)
    client = AGIAgentClient(
        # api_key and model will be read from config/config.txt automatically
        # You can also specify them explicitly: api_key="your_api_key", model="claude-sonnet-4-0"
        debug_mode=False,  # Enable debug logging
        single_task_mode=True  # Use single task mode (recommended)
    )
    
    # Send a chat message (similar to OpenAI API)
    response = client.chat(
        messages=[
            {"role": "user", "content": "Create a simple Python calculator that can add, subtract, multiply and divide"}
        ],
        dir="output_project_01",  # Output directory
        loops=10  # Maximum execution rounds
    )
    
    # Check the result
    if response["success"]:
        print(f"✅ Task completed successfully!")
        print(f"📁 Output directory: {response['output_dir']}")
        print(f"💻 Workspace directory: {response['workspace_dir']}")
        print(f"⏱️ Execution time: {response['execution_time']:.2f} seconds")
    else:
        print(f"❌ Task failed: {response['message']}")
        print(f"📝 Error details: {response['details']}")

def example_with_continue_mode():
    """Example using continue mode to build upon previous work"""
    print("\n=== Continue Mode Example ===")
    
    client = AGIAgentClient(
        # Will read from config/config.txt automatically
    )
    
    # First task: Create basic web app
    print("Step 1: Creating basic web app...")
    response1 = client.chat(
        messages=[
            {"role": "user", "content": "Create a simple Flask web application with a homepage"}
        ],
        dir="my_web_app"
    )
    
    if response1["success"]:
        print("✅ Basic web app created!")
        
        # Second task: Add features to the existing app
        print("Step 2: Adding features to existing app...")
        response2 = client.chat(
            messages=[
                {"role": "user", "content": "Add a contact form and an about page to the existing Flask app"}
            ],
            dir="my_web_app",  # Same directory
            continue_mode=True  # Continue from previous work
        )
        
        if response2["success"]:
            print("✅ Features added successfully!")
            print(f"📁 Final project: {response2['output_dir']}")
        else:
            print(f"❌ Failed to add features: {response2['message']}")
    else:
        print(f"❌ Failed to create basic app: {response1['message']}")

def example_with_custom_config():
    """Example with custom configuration"""
    print("\n=== Custom Configuration Example ===")
    
    # Using the convenience function (will read api_key and model from config/config.txt)
    client = create_client(
        # api_key and model will be read from config/config.txt automatically
        # You can override with: model="claude-3-haiku-20240307"  # Faster, cheaper model
        debug_mode=True,  # Enable detailed logging
        detailed_summary=True,  # Generate detailed reports
        interactive_mode=False,  # Non-interactive execution
        MCP_config_file="config/custom_mcp_servers.json",  # Custom MCP configuration
        prompts_folder="custom_prompts"  # Custom prompts folder
    )
    
    # Check current configuration
    config = client.get_config()
    print(f"Client configuration: {config}")
    
    # Get supported models
    models = client.get_models()
    print(f"Supported models: {models}")
    
    # Execute task
    response = client.chat(
        messages=[
            {"role": "user", "content": "Write a Python script that analyzes CSV files and generates charts"}
        ],
        dir="data_analysis_tool"
    )
    
    print(f"Task result: {'Success' if response['success'] else 'Failed'}")

def example_with_custom_mcp_and_prompts():
    """Example using custom MCP configuration and prompts folder"""
    print("\n=== Custom MCP and Prompts Example ===")
    
    client = AGIAgentClient(
        # api_key and model will be read from config/config.txt automatically
        debug_mode=False,
        MCP_config_file="config/specialized_mcp_servers.json",  # Use specialized MCP tools
        prompts_folder="specialized_prompts"  # Use specialized prompts for different domains
    )
    
    # This allows you to:
    # 1. Use different MCP server configurations for different projects
    # 2. Use different prompt templates and tool interfaces
    # 3. Create domain-specific AGIAgent instances (e.g., for data science, web development, etc.)
    
    response = client.chat(
        messages=[
            {"role": "user", "content": "Create a machine learning pipeline for time series forecasting"}
        ],
        dir="ml_pipeline_project"
    )
    
    if response["success"]:
        print("✅ ML pipeline created with specialized tools and prompts!")
        print(f"📁 Output: {response['output_dir']}")
    else:
        print(f"❌ Failed: {response['message']}")

def example_batch_processing():
    """Example of processing multiple tasks in batch"""
    print("\n=== Batch Processing Example ===")
    
    client = AGIAgentClient(
        # Will read from config/config.txt automatically
    )
    
    tasks = [
        "Create a Python TODO list application",
        "Write a simple weather app using an API"
    ]
    
    results = []
    for i, task in enumerate(tasks, 1):
        print(f"Processing task {i}/{len(tasks)}: {task}")
        
        response = client.chat(
            messages=[{"role": "user", "content": task}],
            dir=f"batch_task_{i}"
        )
        
        results.append({
            "task": task,
            "success": response["success"],
            "output_dir": response["output_dir"] if response["success"] else None,
            "error": response["message"] if not response["success"] else None
        })
        
        print(f"Task {i} {'✅ completed' if response['success'] else '❌ failed'}")
    
    # Summary
    successful = sum(1 for r in results if r["success"])
    print(f"\n📊 Batch processing complete: {successful}/{len(tasks)} tasks successful")
    
    for i, result in enumerate(results, 1):
        status = "✅" if result["success"] else "❌"
        print(f"{status} Task {i}: {result['task'][:50]}...")

def example_thy_test_project():
    """thy test project example"""
    print("=== Thy Test Project Example ===")
    
    # Initialize the client (will automatically read from config/config.txt)
    client = AGIAgentClient(
        # api_key and model will be read from config/config.txt automatically
        # You can also specify them explicitly: api_key="your_api_key", model="claude-sonnet-4-0"
        debug_mode=False,  # Enable debug logging
        single_task_mode=True  # Use single task mode (recommended)
    )
    
    # Send a chat message (similar to OpenAI API)
    """
    response = client.chat(
        messages=[
            {"role": "user", "content": "帮我爬取清华大学招聘网的招聘信息，如果访问不到，就使用适配器或其他任何方式实现爬取，生成详细的文档"}
            ],
        dir="output_thy_test_project07",  # Output directory
        loops=100  # Maximum execution rounds
    )
    """

    
    # response = client.chat(
    #     messages=[
    #         {"role": "user", "content": "帮我做一个只能客服项目，要求全栈完成，全部进行测试，所有功能要完整，要前端界面美观，后段逻辑清晰，使用RAG和GRAPGRAG，还要使用docker，要实现一个庞大的项目。"}
    #         ],
    #     dir="output_thy_test_project33",  # Output directory
    #     loops=100  # Maximum execution rounds
    # )

    response = client.chat(
        messages=[
            {"role": "user", "content": "你好，写一个笑话，中文的"}
            ],
        dir="output_thy_test_project33",  # Output directory
        loops=100  # Maximum execution rounds
    )
    

    """
    response = client.chat(
        messages=[
            {"role": "user", "content": "你需要从零开始设计并实现一个企业级、多租户、实时协作的知识库与工作流自动化平台，系统规模需达到数万行代码以上。该平台需同时融合 Notion 式块编辑文档系统、结构化数据库（表格/看板/日历）、实时多人协作编辑、企业级权限与审计、全文搜索、可视化工作流引擎、跨系统集成能力。系统必须支持多租户隔离（数据/权限/配额/密钥）、复杂组织结构（公司-部门-项目）、细粒度权限控制（精确到页面、Block、数据库字段），并具备完整的审计日志与合规能力。文档编辑器需基于 Block 模型，支持富文本、表格、数据库、评论、任务、引用、模板，并实现实时多人协作（WebSocket + CRDT 或 OT），支持离线编辑、冲突合并、操作回放与版本回滚。系统需内置 结构化数据库能力（字段、视图、过滤、排序、Relation/Rollup/Formula），并确保在大规模数据下仍可进行增量计算与权限裁剪。你还需要实现一个可视化工作流引擎，支持数据触发、条件分支、人工审批、外部 API 调用、幂等与补偿机制，并能对每个流程实例进行完整追踪与重试。平台需提供 企业级全文搜索（文档、数据库、附件），搜索结果必须严格遵守权限裁剪，支持复杂查询语法，并在搜索服务故障后可自动恢复索引一致性。在非功能层面，系统需满足高并发、高可用、可扩展、可观测、安全与合规要求，包括：事件驱动架构、幂等设计、限流熔断、日志/指标/链路追踪、数据加密、审计不可抵赖。你需要输出完整的需求拆解、系统架构设计、数据模型、核心算法设计、服务接口定义、前后端实现方案、测试策略、部署与扩展方案，并确保系统在真实复杂场景（多人协作、权限差异、流程失败补偿、搜索延迟恢复）下仍能正确运行。"}
            ],
        dir="output_thy_test_project",  # Output directory
        loops=100  # Maximum execution rounds
    )
    """

if __name__ == "__main__":
    print("AGI Agent Python Library Examples")
    print("=" * 50)
    
    # Note: Before running these examples, make sure to:
    # 1. Set your API key and model in config/config.txt
    # 2. Install required dependencies
    # 3. Have the src/ directory with the AGIAgent source code
    
    print("ℹ️  Note: These examples will automatically read API key and model from config/config.txt")
    print("   Make sure your config/config.txt file contains valid API_KEY and MODEL settings.")
    print()
    
    # Uncomment the examples you want to run:
    
    # example_basic_usage()
    # example_with_continue_mode()
    # example_with_custom_config()
    # example_with_custom_mcp_and_prompts()
    # example_batch_processing()
    example_thy_test_project()
    
    print("Examples ready to run! Uncomment the function calls above to test.") 