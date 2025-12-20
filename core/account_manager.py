"""
账号管理器
管理多个WeLearn账号的增删改查和导入导出
"""
import json
import csv
import os
import sys
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class Account:
    """账号数据结构"""
    username: str
    password: str
    nickname: str = ""  # 可选的昵称
    status: str = "待处理"  # 待处理/登录中/运行中/已完成/失败
    progress: str = ""  # 进度信息
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'Account':
        return Account(**data)


class AccountManager:
    """账号管理器"""
    
    def __init__(self):
        self.accounts: List[Account] = []
        # 使用更可靠的方式确定数据文件路径
        if getattr(sys, 'frozen', False):
            # 如果是打包后的可执行程序
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller打包
                app_dir = os.path.dirname(sys.executable)
            else:
                # 其他打包方式
                app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        else:
            # 源代码运行
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.data_file = os.path.join(app_dir, "accounts.json")
        print(f"账号数据文件路径: {self.data_file}")  # 添加调试信息
        self.load_accounts()
    
    def add_account(self, username: str, password: str, nickname: str = "") -> bool:
        """添加账号"""
        # 检查是否已存在
        if any(acc.username == username for acc in self.accounts):
            return False
        
        self.accounts.append(Account(username, password, nickname))
        self.save_accounts()
        return True
    
    def remove_account(self, username: str) -> bool:
        """删除账号"""
        for i, acc in enumerate(self.accounts):
            if acc.username == username:
                self.accounts.pop(i)
                self.save_accounts()
                return True
        return False
    
    def clear_accounts(self):
        """清空所有账号"""
        self.accounts.clear()
        self.save_accounts()
    
    def get_account(self, username: str) -> Optional[Account]:
        """获取账号"""
        for acc in self.accounts:
            if acc.username == username:
                return acc
        return None
    
    def get_all_accounts(self) -> List[Account]:
        """获取所有账号"""
        return self.accounts.copy()
    
    def update_status(self, username: str, status: str, progress: str = ""):
        """更新账号状态"""
        acc = self.get_account(username)
        if acc:
            acc.status = status
            acc.progress = progress
            self.save_accounts()
    
    def save_accounts(self):
        """保存账号信息到文件"""
        try:
            # 确保目录存在
            dir_path = os.path.dirname(self.data_file)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                data = {
                    'accounts': [acc.to_dict() for acc in self.accounts]
                }
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"成功保存 {len(self.accounts)} 个账号到: {self.data_file}")
            return True
        except Exception as e:
            print(f"保存账号信息失败: {e}")
            print(f"尝试保存到: {self.data_file}")
            return False
    
    def load_accounts(self):
        """从文件加载账号信息"""
        if not os.path.exists(self.data_file):
            print(f"账号数据文件不存在: {self.data_file}")
            return
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'accounts' in data:
                    self.accounts = [Account.from_dict(acc) for acc in data['accounts']]
                    print(f"成功加载 {len(self.accounts)} 个账号")
                else:
                    print("账号数据文件格式错误：缺少 'accounts' 字段")
                    self.accounts = []
        except Exception as e:
            print(f"加载账号信息失败: {e}")
            print(f"尝试加载的文件: {self.data_file}")
            self.accounts = []
    
    def import_from_file(self, filepath: str) -> tuple[int, str]:
        """
        从文件导入账号
        支持格式：
        - CSV: username,password,nickname
        - TXT: username,password 每行一个
        
        返回: (成功导入数量, 错误信息)
        """
        try:
            imported_count = 0
            
            if filepath.endswith('.csv'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 2:
                            username = row[0].strip()
                            password = row[1].strip()
                            nickname = row[2].strip() if len(row) > 2 else ""
                            
                            if self.add_account(username, password, nickname):
                                imported_count += 1
            
            elif filepath.endswith('.txt'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        parts = line.split(',')
                        if len(parts) >= 2:
                            username = parts[0].strip()
                            password = parts[1].strip()
                            nickname = parts[2].strip() if len(parts) > 2 else ""
                            
                            if self.add_account(username, password, nickname):
                                imported_count += 1
            
            else:
                return 0, "不支持的文件格式，请使用 .csv 或 .txt"
            
            return imported_count, ""
        
        except Exception as e:
            return 0, f"导入失败: {str(e)}"
    
    def export_to_file(self, filepath: str) -> tuple[bool, str]:
        """
        导出账号到文件
        
        返回: (是否成功, 错误信息)
        """
        try:
            if filepath.endswith('.csv'):
                with open(filepath, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['用户名', '密码', '昵称'])
                    for acc in self.accounts:
                        writer.writerow([acc.username, acc.password, acc.nickname])
            
            elif filepath.endswith('.txt'):
                with open(filepath, 'w', encoding='utf-8') as f:
                    for acc in self.accounts:
                        f.write(f"{acc.username},{acc.password},{acc.nickname}\n")
            
            else:
                return False, "不支持的文件格式，请使用 .csv 或 .txt"
            
            return True, ""
        
        except Exception as e:
            return False, f"导出失败: {str(e)}"
    
    def reset_all_status(self):
        """重置所有账号状态"""
        for acc in self.accounts:
            acc.status = "待处理"
            acc.progress = ""
    
    def get_account_count(self) -> int:
        """获取账号数量"""
        return len(self.accounts)
