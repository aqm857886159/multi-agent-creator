"""
外部记忆系统 (External Memory System)

基于 Manus Context Engineering 最佳实践实现
"""

from .file_memory import (
    FileMemory,
    get_file_memory,
    should_compress,
    compress_candidates_if_needed
)

__all__ = [
    "FileMemory",
    "get_file_memory", 
    "should_compress",
    "compress_candidates_if_needed"
]

