"""
文件系统外部记忆机制 (File System External Memory)

基于 Manus Context Engineering 最佳实践:
- 将文件系统作为终极上下文，大小不受限制
- 压缩策略设计为可恢复的（只保留 URL，内容可重新获取）
- 模型学会按需写入和读取文件

核心功能:
1. 候选内容外部化存储
2. 可恢复压缩（只保留引用）
3. 按需加载机制
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FileMemory:
    """文件系统外部记忆管理器"""
    
    def __init__(self, base_dir: str = "data/memory"):
        self.base_dir = Path(base_dir)
        self.candidates_dir = self.base_dir / "candidates"
        self.leads_dir = self.base_dir / "leads"
        self.scratchpad_dir = self.base_dir / "scratchpad"
        self.index_file = self.base_dir / "index.json"
        
        # 创建目录
        self._ensure_dirs()
        
        # 加载索引
        self.index = self._load_index()
    
    def _ensure_dirs(self):
        """确保目录存在"""
        for dir_path in [self.candidates_dir, self.leads_dir, self.scratchpad_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _load_index(self) -> Dict[str, Any]:
        """加载索引文件"""
        if self.index_file.exists():
            try:
                return json.loads(self.index_file.read_text(encoding='utf-8'))
            except Exception as e:
                logger.warning(f"Failed to load index: {e}")
        return {
            "candidates": {},
            "leads": {},
            "scratchpad": [],
            "stats": {
                "total_candidates": 0,
                "total_leads": 0,
                "last_updated": None
            }
        }
    
    def _save_index(self):
        """保存索引文件"""
        self.index["stats"]["last_updated"] = datetime.now().isoformat()
        self.index_file.write_text(
            json.dumps(self.index, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    
    def _generate_id(self, content: Dict[str, Any]) -> str:
        """生成内容唯一ID（基于URL或内容hash）"""
        url = content.get("url", "")
        if url:
            return hashlib.md5(url.encode()).hexdigest()[:12]
        # 如果没有URL，使用内容hash
        content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content_str.encode()).hexdigest()[:12]
    
    # ============ 候选内容管理 ============
    
    def store_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        存储候选内容到文件系统
        
        Args:
            candidates: 完整的候选内容列表
            
        Returns:
            压缩后的引用列表（只包含 URL 和元数据）
        """
        compressed = []
        
        for item in candidates:
            item_id = self._generate_id(item)
            
            # 存储完整数据
            file_path = self.candidates_dir / f"{item_id}.json"
            file_path.write_text(
                json.dumps(item, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            
            # 更新索引
            self.index["candidates"][item_id] = {
                "url": item.get("url", ""),
                "title": item.get("title", "")[:50],
                "platform": item.get("platform", "unknown"),
                "file": str(file_path.relative_to(self.base_dir)),
                "stored_at": datetime.now().isoformat()
            }
            
            # 创建压缩引用
            compressed.append({
                "_ref_id": item_id,
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "platform": item.get("platform", ""),
                "view_count": item.get("view_count", 0),
                "score": item.get("score", 0.0),
                # 其他核心字段保留，详细数据外部化
            })
        
        self.index["stats"]["total_candidates"] = len(self.index["candidates"])
        self._save_index()
        
        logger.info(f"Stored {len(candidates)} candidates to file system")
        return compressed
    
    def load_candidate(self, ref_id: str) -> Optional[Dict[str, Any]]:
        """
        按需加载单个候选内容
        
        Args:
            ref_id: 引用ID
            
        Returns:
            完整的候选内容数据
        """
        if ref_id not in self.index["candidates"]:
            logger.warning(f"Candidate {ref_id} not found in index")
            return None
        
        file_path = self.base_dir / self.index["candidates"][ref_id]["file"]
        if not file_path.exists():
            logger.warning(f"Candidate file not found: {file_path}")
            return None
        
        try:
            return json.loads(file_path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.error(f"Failed to load candidate {ref_id}: {e}")
            return None
    
    def load_candidates_batch(self, ref_ids: List[str]) -> List[Dict[str, Any]]:
        """批量加载候选内容"""
        results = []
        for ref_id in ref_ids:
            item = self.load_candidate(ref_id)
            if item:
                results.append(item)
        return results
    
    def get_all_candidate_refs(self) -> List[Dict[str, Any]]:
        """获取所有候选内容的引用（不加载完整数据）"""
        return [
            {"_ref_id": ref_id, **meta}
            for ref_id, meta in self.index["candidates"].items()
        ]
    
    # ============ Leads 管理 ============
    
    def store_leads(self, leads: List[Dict[str, Any]]) -> int:
        """存储线索到文件系统"""
        stored = 0
        for item in leads:
            item_id = self._generate_id(item)
            
            file_path = self.leads_dir / f"{item_id}.json"
            file_path.write_text(
                json.dumps(item, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            
            self.index["leads"][item_id] = {
                "url": item.get("url", ""),
                "title": item.get("title", "")[:50],
                "source": item.get("source", "unknown"),
                "file": str(file_path.relative_to(self.base_dir)),
                "stored_at": datetime.now().isoformat()
            }
            stored += 1
        
        self.index["stats"]["total_leads"] = len(self.index["leads"])
        self._save_index()
        
        return stored
    
    # ============ Scratchpad 管理 ============
    
    def append_scratchpad(self, entry: Dict[str, Any]) -> str:
        """
        追加 scratchpad 条目（Manus: 上下文只追加，不修改历史）
        
        Returns:
            条目文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_path = self.scratchpad_dir / f"{timestamp}.json"
        
        entry_with_meta = {
            "timestamp": datetime.now().isoformat(),
            **entry
        }
        
        file_path.write_text(
            json.dumps(entry_with_meta, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        
        self.index["scratchpad"].append({
            "file": str(file_path.relative_to(self.base_dir)),
            "timestamp": entry_with_meta["timestamp"],
            "type": entry.get("type", "unknown")
        })
        self._save_index()
        
        return str(file_path)
    
    def get_recent_scratchpad(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的 scratchpad 条目"""
        recent_refs = self.index["scratchpad"][-limit:]
        results = []
        
        for ref in recent_refs:
            file_path = self.base_dir / ref["file"]
            if file_path.exists():
                try:
                    results.append(json.loads(file_path.read_text(encoding='utf-8')))
                except Exception:
                    pass
        
        return results
    
    # ============ 压缩与恢复 ============
    
    def compress_state(self, state: Dict[str, Any], threshold: int = 100) -> Dict[str, Any]:
        """
        压缩状态（当数据量超过阈值时外部化存储）
        
        Args:
            state: 完整状态字典
            threshold: 触发压缩的阈值
            
        Returns:
            压缩后的状态（大数据替换为引用）
        """
        compressed_state = state.copy()
        
        # 压缩 candidates
        candidates = state.get("candidates", [])
        if len(candidates) > threshold:
            logger.info(f"Compressing {len(candidates)} candidates (threshold: {threshold})")
            compressed_refs = self.store_candidates(candidates)
            compressed_state["candidates"] = compressed_refs
            compressed_state["_candidates_externalized"] = True
        
        # 压缩 leads
        leads = state.get("leads", [])
        if len(leads) > threshold:
            logger.info(f"Compressing {len(leads)} leads")
            self.store_leads(leads)
            # leads 只保留最近的
            compressed_state["leads"] = leads[-20:]
            compressed_state["_leads_externalized"] = True
        
        return compressed_state
    
    def restore_candidates(self, compressed_refs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        恢复压缩的候选内容
        
        Args:
            compressed_refs: 压缩的引用列表
            
        Returns:
            完整的候选内容列表
        """
        ref_ids = [item.get("_ref_id") for item in compressed_refs if item.get("_ref_id")]
        return self.load_candidates_batch(ref_ids)
    
    # ============ 统计与清理 ============
    
    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        return {
            "total_candidates": self.index["stats"]["total_candidates"],
            "total_leads": self.index["stats"]["total_leads"],
            "scratchpad_entries": len(self.index["scratchpad"]),
            "last_updated": self.index["stats"]["last_updated"],
            "storage_path": str(self.base_dir.absolute())
        }
    
    def cleanup_old_data(self, days: int = 7):
        """清理旧数据（保留最近 N 天）"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        cleaned = 0
        for ref_id, meta in list(self.index["candidates"].items()):
            stored_at = datetime.fromisoformat(meta["stored_at"])
            if stored_at < cutoff:
                file_path = self.base_dir / meta["file"]
                if file_path.exists():
                    file_path.unlink()
                del self.index["candidates"][ref_id]
                cleaned += 1
        
        if cleaned > 0:
            self._save_index()
            logger.info(f"Cleaned up {cleaned} old candidates")
        
        return cleaned


# ============ 全局实例 ============

_file_memory: Optional[FileMemory] = None

def get_file_memory() -> FileMemory:
    """获取全局 FileMemory 实例"""
    global _file_memory
    if _file_memory is None:
        _file_memory = FileMemory()
    return _file_memory


# ============ 便捷函数 ============

def should_compress(candidates_count: int, threshold: int = 100) -> bool:
    """判断是否需要压缩"""
    return candidates_count > threshold

def compress_candidates_if_needed(
    candidates: List[Dict[str, Any]], 
    threshold: int = 100
) -> tuple[List[Dict[str, Any]], bool]:
    """
    按需压缩候选内容
    
    Returns:
        (压缩后的列表或原列表, 是否进行了压缩)
    """
    if len(candidates) <= threshold:
        return candidates, False
    
    memory = get_file_memory()
    compressed = memory.store_candidates(candidates)
    return compressed, True

