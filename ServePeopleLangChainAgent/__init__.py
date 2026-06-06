"""
HowToServePeopleLangChainAgent — Multi-Agent Job Search System

    from ServePeopleLangChainAgent import run
    answer = run("男，2019年毕业，计算机科学与技术，想找山西太原考公岗位")
"""
from .orchestrator import run, run_async, run_stream, get_ceo_agent
from . import config, tools, prompts, agents, orchestrator

__all__ = ["run", "run_async", "run_stream", "get_ceo_agent",
           "config", "tools", "prompts", "agents", "orchestrator"]
