"""日志配置模块"""
import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

class RunLogger:
    def __init__(self, base_dir: str = "logs"):
        self.base_dir = Path(base_dir)
        self.runs_dir = self.base_dir / "runs"
        self.history_file = self.base_dir / "history.json"
        
        # 创建必要的目录
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化历史记录文件
        if not self.history_file.exists():
            self._save_history({})
    
    def start_new_run(self, run_type: str = "scheduled") -> str:
        """开始新的运行记录"""
        run_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()
        
        run_info = {
            "run_id": run_id,
            "type": run_type,
            "start_time": timestamp,
            "status": "running",
            "items_count": 0,
            "duration_seconds": 0,
            "log_file": f"runs/run_{run_id}.log"
        }
        
        # 更新历史记录
        history = self._load_history()
        history[run_id] = run_info
        self._save_history(history)
        
        return run_id
    
    def update_run(self, run_id: str, **kwargs) -> None:
        """更新运行记录"""
        history = self._load_history()
        if run_id in history:
            history[run_id].update(kwargs)
            if "end_time" in kwargs:
                # 计算运行时长
                start = datetime.fromisoformat(history[run_id]["start_time"])
                end = datetime.fromisoformat(kwargs["end_time"])
                history[run_id]["duration_seconds"] = (end - start).total_seconds()
            self._save_history(history)
    
    def get_run_log_path(self, run_id: str) -> Path:
        """获取运行日志文件路径"""
        return self.runs_dir / f"run_{run_id}.log"
    
    def get_all_runs(self, limit: int = 50) -> Dict:
        """获取所有运行记录"""
        history = self._load_history()
        # 按开始时间倒序排序并限制数量
        sorted_runs = dict(sorted(
            history.items(),
            key=lambda x: x[1]["start_time"],
            reverse=True
        )[:limit])
        return sorted_runs
    
    def _load_history(self) -> Dict:
        """加载历史记录"""
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_history(self, history: Dict) -> None:
        """保存历史记录"""
        with open(self.history_file, 'w') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
