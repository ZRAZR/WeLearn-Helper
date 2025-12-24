"""
WeLearn 自动学习工具 - 主窗口
多用户管理中心
"""
import os
import sys
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QMenuBar, QMenu, QAction,
    QMessageBox, QStatusBar, QSystemTrayIcon, QApplication, QStyle
)
from PyQt5.QtGui import QIcon, QBitmap, QPixmap, QPainter, QBrush

# 直接导入模块，避免使用ui前缀
import sys
import os

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 直接导入模块
from ui import account_view
from ui import account_detail
from core import account_manager
AccountView = account_view.AccountView
AccountDetailDialog = account_detail.AccountDetailDialog
Account = account_manager.Account


class WeLearnUI(QMainWindow):
    """
    主窗口
    现在作为多用户管理中心
    """
    
    def __init__(self):
        super().__init__()
        self.detail_dialogs = {}  # 存储打开的详情对话框
        self.tray_icon = None     # 系统托盘图标
        self.tray_reminder_timer = None  # 托盘提醒定时器
        self.version = "V5.0.11"     # 软件版本号
        self.init_ui()
        self.init_tray()  # 初始化系统托盘
        
        self.show_startup_warning()  # 显示启动警告
        self.show_update_announcement()  # 显示更新公告

    
    def center_window(self):
        """将窗口居中显示在屏幕中央"""
        screen = QApplication.desktop().screenGeometry()
        window_frame = self.frameGeometry()
        x = (screen.width() - window_frame.width()) // 2
        y = (screen.height() - window_frame.height()) // 2
        self.move(x, y)
    
    def show(self):
        """重写show方法，在显示窗口后居中"""
        from core.logger import get_logger
        logger = get_logger("MainWindow")
        logger.info("主窗口show方法被调用")
        
        super().show()
        QTimer.singleShot(100, self.center_window)
        # 窗口显示后立即检查未完成的任务
        logger.info("准备在100ms后检查未完成的任务")
        QTimer.singleShot(100, self.check_incomplete_tasks)
    
    def init_ui(self):
        self.setWindowTitle("ZR | WeLearn学习助手 V5.0.11    致力于把大学生的时间还给大学生")
        self.setGeometry(100, 100, 900, 600)
        self.setMinimumSize(800, 500)
        
        # 获取应用根目录
        app_dir = self.get_app_directory()
        
        # 设置窗口图标
        icon_path = os.path.join(app_dir, 'ZR.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            print(f"已设置窗口图标: {icon_path}")
        else:
            print(f"图标文件不存在: {icon_path}")
        
        # 设置背景图片
        bg_path = os.path.join(app_dir, 'ZR.png')
        if os.path.exists(bg_path):
            palette = self.palette()
            pixmap = QPixmap(bg_path)
            palette.setBrush(self.backgroundRole(), QBrush(pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)))
            self.setPalette(palette)
            print(f"已设置背景图片: {bg_path}")
        else:
            print(f"背景图片文件不存在: {bg_path}")
        
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: rgba(255, 255, 255, 0.8);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                font-size: 13px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.8);
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: black;
            }
            QHeaderView::section {
                background-color: rgba(240, 240, 240, 0.8);
                padding: 8px;
                border: none;
                border-bottom: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        self.account_view = AccountView()
        self.account_view.open_detail_requested.connect(self.open_account_detail)
        self.setCentralWidget(self.account_view)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 - 添加账号开始使用")
        
        from PyQt5.QtWidgets import QLabel
        disclaimer_label = QLabel("本软件仅供学术交流，禁止用于商业途径")
        disclaimer_label.setStyleSheet("color: red; font-size: 14px; font-weight: bold; padding: 2px;")
        self.status_bar.addPermanentWidget(disclaimer_label)
    
    def create_menu_bar(self):
        """创建菜单栏"""
        pass
    
    def open_account_detail(self, account: Account):
        """打开账号详情对话框"""
        username = account.username
        
        if username in self.detail_dialogs:
            dialog = self.detail_dialogs[username]
            if dialog.isVisible():
                dialog.raise_()
                dialog.activateWindow()
                return
            else:
                del self.detail_dialogs[username]
        
        dialog = AccountDetailDialog(account, self)
        dialog.status_updated.connect(self.on_account_status_updated)
        dialog.finished.connect(lambda result, u=username: self.on_detail_closed(u))
        
        self.detail_dialogs[username] = dialog
        dialog.show()
        self.status_bar.showMessage(f"已打开账号详情: {username}")
    
    def on_account_status_updated(self, username: str, status: str, progress: str):
        """账号状态更新回调"""
        self.account_view.update_account_status(username, status, progress)
    
    def on_detail_closed(self, username: str):
        """详情对话框关闭回调"""
        if username in self.detail_dialogs:
            del self.detail_dialogs[username]
        self.account_view.refresh_table()
    
    def show_about(self):
        """显示关于对话框"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("关于 WeLearn 自动学习工具")
        msg_box.setIcon(QMessageBox.Information)
        # 移除问号帮助按钮
        msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 设置样式
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #f0f0f0;
            }
            QMessageBox QLabel {
                background-color: rgba(255, 255, 255, 220);
                padding: 10px;
                border-radius: 5px;
            }
            QMessageBox QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 13px;
                border-radius: 4px;
            }
            QMessageBox QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        msg_box.setText(
            """
            <h3>WeLearn 自动学习工具</h3>
            <p>版本: 2.1 (ZR修改版)</p>
            <p>软件仅供学习参考使用，禁止用于一切商业用途</p>
            <p>禁止使用软件进行任何代刷牟利，以此造成的任何问题本人不负责任</p>
            """
        )
        msg_box.setStandardButtons(QMessageBox.Ok)
        
        msg_box.show()
        msg_box.setGeometry(
            QStyle.alignedRect(
                Qt.LeftToRight,
                Qt.AlignCenter,
                msg_box.size(),
                QApplication.desktop().availableGeometry()
            )
        )
        
        msg_box.exec_()
    
    def open_github(self):
        """打开 GitHub 项目页面"""
        import webbrowser
        webbrowser.open("https://github.com/jhl337/Auto_WeLearn/")
    
    def check_incomplete_tasks(self):
        """检查未完成的任务"""
        from core.task_progress import TaskProgress
        from core.logger import get_logger
        
        logger = get_logger("MainWindow")
        logger.info("开始检查未完成的任务")
        
        # 创建任务进度管理器
        progress_manager = TaskProgress()
        
        # 获取所有未完成的任务
        incomplete_tasks = progress_manager.get_incomplete_tasks()
        
        if incomplete_tasks:
            logger.info(f"发现 {len(incomplete_tasks)} 个未完成的任务")
            print(f"发现 {len(incomplete_tasks)} 个未完成的任务，准备显示恢复对话框")
            # 立即显示对话框，与主UI同时显示
            self.show_task_resume_dialog(incomplete_tasks)
        else:
            logger.info("没有发现未完成的任务")
            print("没有发现未完成的任务")
    
    def show_task_resume_dialog(self, incomplete_tasks):
        """显示任务恢复对话框"""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                                     QStyle, QListWidget, QListWidgetItem, 
                                     QCheckBox, QHBoxLayout, QWidget)
        from PyQt5.QtCore import Qt
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("未完成任务")
        dialog.setMinimumSize(700, 450)
        dialog.resize(700, 450)
        # 移除问号帮助按钮
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 创建主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 添加提示文本
        message = QLabel(f"发现 {len(incomplete_tasks)} 个未完成的任务，请勾选要继续的任务：")
        message.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(message)
        
        # 添加任务列表
        task_list = QListWidget()
        task_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
                min-height: 40px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
        
        # 添加任务项到列表
        for i, task in enumerate(incomplete_tasks):
            task_type = task.get('task_type', '未知任务')
            task_id = task.get('task_id', 'N/A')
            last_update = task.get('last_update_time_str', '未知时间')
            
            # 从任务ID中提取用户名
            parts = task_id.split('_')
            username = parts[0] if len(parts) >= 4 else '未知用户'
            
            # 创建自定义列表项，包含勾选框
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 5, 5, 5)
            
            # 添加勾选框
            checkbox = QCheckBox()
            checkbox.setChecked(False)  # 默认不勾选
            checkbox.setProperty("task_index", i)  # 存储任务索引
            
            # 添加任务信息标签
            item_text = f"{task_type} - {username} (最后更新: {last_update})"
            label = QLabel(item_text)
            label.setWordWrap(True)  # 允许文本换行
            label.setStyleSheet("font-size: 12px;")
            
            item_layout.addWidget(checkbox)
            item_layout.addWidget(label, 1)  # 1表示拉伸因子
            
            # 创建列表项并设置自定义控件
            item = QListWidgetItem(task_list)
            item.setSizeHint(item_widget.sizeHint())
            task_list.setItemWidget(item, item_widget)
            item.setData(Qt.UserRole, i)  # 存储任务在列表中的索引
        
        layout.addWidget(task_list)
        
        # 添加按钮
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        
        continue_button = QPushButton("继续勾选的任务")
        continue_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        continue_button.clicked.connect(lambda: self.resume_selected_task(task_list, incomplete_tasks, dialog))
        button_layout.addWidget(continue_button)
        
        delete_button = QPushButton("删除所有任务")
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        delete_button.clicked.connect(lambda: self.delete_task_progress(incomplete_tasks, dialog))
        button_layout.addWidget(delete_button)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        # 居中显示对话框
        dialog.show()
        dialog.setGeometry(
            QStyle.alignedRect(
                Qt.LeftToRight,
                Qt.AlignCenter,
                dialog.size(),
                QApplication.desktop().availableGeometry()
            )
        )
        
        # 使用非阻塞方式显示对话框
        dialog.open()
    
    def resume_selected_task(self, task_list, incomplete_tasks, dialog):
        """恢复勾选的任务"""
        print("\n" + "="*60)
        print("🔍 开始 resume_selected_task")
        print("="*60)
        
        from core.logger import get_logger
        from PyQt5.QtWidgets import QMessageBox, QCheckBox
        
        logger = get_logger("MainWindow")
        
        # 关闭对话框
        print("✅ 准备关闭对话框")
        dialog.accept()
        print("✅ 对话框已关闭")
        
        # 查找所有勾选的任务
        selected_indices = []
        print(f"✅ 开始检查勾选的任务，总任务数: {len(incomplete_tasks)}")
        
        for i in range(task_list.count()):
            item = task_list.item(i)
            item_widget = task_list.itemWidget(item)
            if item_widget:
                # 获取勾选框
                checkbox = item_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    task_index = checkbox.property("task_index")
                    if task_index is not None and task_index < len(incomplete_tasks):
                        selected_indices.append(task_index)
                        task_data = incomplete_tasks[task_index]
                        task_id = task_data.get('task_id', '未知ID')
                        username = task_data.get('username', '未知用户')
                        print(f"✅ 选中任务: {task_id} (用户: {username})")
        
        if not selected_indices:
            print("❌ 没有选中的任务")
            QMessageBox.warning(dialog, "提示", "请至少勾选一个任务！")
            logger.info("没有选择要继续的任务")
            return
        
        print(f"准备恢复 {len(selected_indices)} 个任务")
        
        # 如果选择了多个任务，只恢复第一个（因为一次只能运行一个任务）
        if len(selected_indices) > 1:
            print(f"⚠️ 选择了多个任务({len(selected_indices)}个)，只恢复第一个")
            reply = QMessageBox.question(
                dialog, 
                "确认", 
                f"您勾选了 {len(selected_indices)} 个任务，但一次只能恢复一个任务。是否恢复第一个勾选的任务？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                print("❌ 用户取消多任务恢复")
                return
        
        selected_index = selected_indices[0]
        selected_task = incomplete_tasks[selected_index]
        task_id = selected_task.get('task_id', '未知ID')
        username = selected_task.get('username', '未知用户')
        
        print(f"\n--- 处理任务 ---")
        print(f"任务数据: {selected_task}")
        print(f"任务ID: {task_id}")
        print(f"用户名: {username}")
        
        logger.info(f"选择了任务 {task_id} 进行恢复")
        
        # 恢复选中的任务
        try:
            print(f"✅ 准备调用 resume_task")
            self.resume_task(selected_task, None)
            print(f"✅ 已调用 resume_task")
        except Exception as e:
            print(f"❌ 恢复任务时发生错误: {e}")
            import traceback
            traceback.print_exc()
            
            import traceback
            error_msg = f"继续任务时发生错误: {str(e)}\n\n详细信息:\n{traceback.format_exc()}"
            logger.error(f"恢复任务失败: {error_msg}")
            
            # 创建错误对话框，保持窗口打开以便复制错误信息
            from PyQt5.QtWidgets import QCheckBox
            error_dialog = QMessageBox(dialog)
            error_dialog.setWindowTitle("错误")
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setText("继续任务时发生错误")
            error_dialog.setDetailedText(error_msg)
            error_dialog.setStandardButtons(QMessageBox.Ok)
            error_dialog.setDefaultButton(QMessageBox.Ok)
            
            # 添加复选框，让用户选择是否保持窗口打开
            checkbox = QCheckBox("保持窗口打开以便复制错误信息")
            error_dialog.setCheckBox(checkbox)
            
            # 显示错误对话框
            error_dialog.exec_()
            
            # 如果用户勾选了复选框，再次显示错误对话框
            if checkbox.isChecked():
                error_dialog.setText("错误信息已保留，您可以复制错误信息")
                error_dialog.setDetailedText(error_msg)
                error_dialog.exec_()
        
        print("="*60)
        print("🔍 resume_selected_task 执行完成")
        print("="*60 + "\n")
    
    def resume_task(self, task_data, dialog):
        """恢复任务
        
        Args:
            task_data: 任务数据
            dialog: 对话框对象
        """
        from core.account_manager import AccountManager
        from core.logger import get_logger
        
        logger = get_logger("MainWindow")
        
        # 如果有对话框，则关闭它
        if dialog:
            dialog.accept()
        
        # 获取任务相关的账号信息
        task_id = task_data.get('task_id')
        if not task_id:
            logger.error("任务ID为空，无法恢复任务")
            return
        
        # 🔧 现在可以使用保存的username字段
        username = task_data.get('username')
        
        # 添加调试信息
        logger.info(f"任务数据完整内容: {task_data}")
        logger.info(f"提取的username: {username}")
        
        if not username:
            logger.error(f"任务数据中缺少username: {task_data}")
            # 尝试从task_id中解析作为备用方案
            task_id = task_data.get('task_id', '')
            if '_' in task_id:
                parts = task_id.split('_')
                if len(parts) >= 2:
                    username = parts[0]
                    logger.warning(f"使用备用方案从task_id解析username: {username}")
            else:
                logger.error(f"无法从task_id解析username: {task_id}")
                return
        
        # 获取账号管理器
        account_manager = AccountManager()
        
        # 查找对应的账号
        accounts = account_manager.get_all_accounts()
        target_account = None
        
        for account in accounts:
            if account.username == username:
                target_account = account
                break
        
        if not target_account:
            logger.error(f"未找到用户名为 {username} 的账号")
            return
        
        logger.info(f"找到账号: {target_account.username}，准备恢复任务")
        
        # 打开账号详情对话框并传递任务数据
        self.open_account_detail_with_resume(target_account, task_data)
    
    def delete_task_progress(self, incomplete_tasks, dialog):
        """删除任务进度"""
        from core.task_progress import TaskProgress
        from core.logger import get_logger
        from PyQt5.QtWidgets import QMessageBox
        
        logger = get_logger("MainWindow")
        
        # 关闭对话框
        dialog.accept()
        
        # 创建任务进度管理器
        progress_manager = TaskProgress()
        
        # 删除所有未完成的任务
        deleted_count = 0
        for task in incomplete_tasks:
            task_id = task.get('task_id')
            if task_id:
                success = progress_manager.clear_task_progress(task_id)
                if success:
                    logger.info(f"已删除任务进度: {task_id}")
                    deleted_count += 1
                else:
                    logger.error(f"删除任务进度失败: {task_id}")
        
        # 显示删除结果
        if deleted_count > 0:
            QMessageBox.information(self, "任务已删除", f"已成功删除 {deleted_count} 个未完成的任务")
            logger.info(f"用户选择删除任务，共删除 {deleted_count} 个任务")
        else:
            QMessageBox.warning(self, "删除失败", "未能删除任何任务进度")
            logger.warning("用户选择删除任务，但未能删除任何任务")
    
    def open_account_detail_with_resume(self, account, resume_task_data):
        """打开账号详情对话框并传递恢复任务数据
        
        Args:
            account: 账号对象
            resume_task_data: 恢复任务数据
        """
        print("\n" + "-"*50)
        print("🔍 开始 open_account_detail_with_resume")
        print(f"账号: {account.username}")
        print(f"任务数据: {resume_task_data}")
        print("-"*50)
        
        from core.logger import get_logger
        logger = get_logger("MainWindow")
        
        username = account.username
        logger.info(f"准备打开账号详情对话框并恢复任务 - 用户名: {username}")
        
        if username in self.detail_dialogs:
            dialog = self.detail_dialogs[username]
            if dialog.isVisible():
                print(f"⚠️ 详情页已存在，激活窗口")
                dialog.raise_()
                dialog.activateWindow()
                logger.info(f"账号详情对话框已存在且可见，激活窗口 - 用户名: {username}")
                return
            else:
                print(f"⚠️ 详情页存在但不可见，删除旧实例")
                del self.detail_dialogs[username]
        
        # 创建账号详情对话框并传递恢复任务数据
        print(f"✅ 创建新的 AccountDetailDialog")
        try:
            dialog = AccountDetailDialog(account, self, resume_task_data=resume_task_data)
            print(f"✅ 对话框创建成功")
        except Exception as e:
            print(f"❌ 创建对话框失败: {e}")
            import traceback
            traceback.print_exc()
            return
        
        dialog.status_updated.connect(self.on_account_status_updated)
        dialog.finished.connect(lambda result, u=username: self.on_detail_closed(u))
        
        self.detail_dialogs[username] = dialog
        
        # 显示对话框并确保它在前台
        print(f"✅准备显示对话框")
        dialog.show()
        print(f"✅ 对话框已调用show()")
        
        # 使用定时器多次确保对话框在前台
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._ensure_dialog_foreground(dialog))
        QTimer.singleShot(500, lambda: self._ensure_dialog_foreground(dialog))
        QTimer.singleShot(1000, lambda: self._ensure_dialog_foreground(dialog))
        
        self.status_bar.showMessage(f"已打开账号详情: {username} (恢复任务)")
        logger.info(f"账号详情对话框已打开 - 用户名: {username}")
        
        print(f"✅ open_account_detail_with_resume 执行完成")
        print("-"*50 + "\n")
    
    def _ensure_dialog_foreground(self, dialog):
        """确保对话框在前台显示"""
        try:
            if dialog.isVisible():
                dialog.raise_()
                dialog.activateWindow()
                dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
                dialog.show()
                dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowStaysOnTopHint)
                dialog.show()
                from core.logger import get_logger
                logger = get_logger("MainWindow")
                logger.info(f"已确保对话框在前台显示")
        except Exception as e:
            from core.logger import get_logger
            logger = get_logger("MainWindow")
            logger.error(f"确保对话框在前台显示时出错: {str(e)}")
            from core.logger import get_logger
            logger = get_logger("MainWindow")
            logger.error(f"确保对话框在前台显示时出错: {str(e)}")
    
    def get_app_directory(self):
        """获取应用根目录（考虑打包后的环境）"""
        if getattr(sys, 'frozen', False):
            # 打包后的环境
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller临时目录
                app_path = sys._MEIPASS
                print(f"PyInstaller临时目录: {app_path}")
                return app_path
            
            # 尝试从可执行文件目录获取
            app_path = os.path.dirname(sys.executable)
            print(f"可执行文件目录: {app_path}")
            
            # 检查图标文件是否在当前目录
            icon_path = os.path.join(app_path, 'ZR.ico')
            if os.path.exists(icon_path):
                return app_path
                
            # 如果不在当前目录，尝试_internal目录（PyInstaller新版本）
            internal_path = os.path.join(app_path, '_internal')
            if os.path.exists(os.path.join(internal_path, 'ZR.ico')):
                print(f"使用_internal目录: {internal_path}")
                return internal_path
                
            return app_path
        else:
            # 开发环境，返回项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            print(f"开发环境项目根目录: {parent_dir}")
            return parent_dir

    def show_startup_warning(self):
        """显示启动警告"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("使用声明")
        msg_box.setIcon(QMessageBox.Warning)
        # 移除问号帮助按钮
        msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 获取应用目录（考虑打包后的环境）
        app_dir = self.get_app_directory()
        background_path = os.path.join(app_dir, 'ZR.png')
        print(f"启动警告获取到的背景图片路径: {background_path}")
        
        if background_path and os.path.exists(background_path):
            # 确保路径使用正斜杠，即使在Windows上
            background_path = background_path.replace("\\", "/")
            print(f"启动警告处理后的背景图片路径: {background_path}")
            
            msg_box.setStyleSheet(f"""
                QMessageBox {{
                    background-image: url(file:///{background_path});
                    background-position: center;
                    background-repeat: no-repeat;
                    background-attachment: fixed;
                }}
                QMessageBox QLabel {{
                    background-color: rgba(255, 255, 255, 220);
                    padding: 10px;
                    border-radius: 5px;
                }}
                QMessageBox QPushButton {{
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-size: 13px;
                    border-radius: 4px;
                }}
                QMessageBox QPushButton:hover {{
                    background-color: #45a049;
                }}
            """)
        else:
            # 如果没有背景图片，使用纯色背景
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #f0f0f0;
                }
                QMessageBox QLabel {
                    background-color: rgba(255, 255, 255, 220);
                    padding: 10px;
                    border-radius: 5px;
                }
                QMessageBox QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-size: 13px;
                    border-radius: 4px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        
        warning_text = """版权声明：

本软件为WeLearn学习助手V5.0.11版本，由ZR修改并打包。

使用条款：
1. 本软件仅供学习交流使用，严禁用于任何商业用途
2. 软件版权归原开发者所有，本修改版仅作功能优化
3. 用户使用本软件所产生的任何后果由用户自行承担
4. 分发本软件时请保持版权信息完整

感谢您的理解与支持！"""
        msg_box.setText(warning_text)
        
        ok_button = msg_box.addButton("我已了解", QMessageBox.AcceptRole)
        msg_box.setDefaultButton(ok_button)
        
        msg_box.show()
        msg_box.setGeometry(
            QStyle.alignedRect(
                Qt.LeftToRight,
                Qt.AlignCenter,
                msg_box.size(),
                QApplication.desktop().availableGeometry()
            )
        )
        
        msg_box.exec_()
    
    def show_update_announcement(self):
        """显示更新公告"""
        # 检查是否已经选择不再提醒
        from PyQt5.QtCore import QSettings
        import os
        import uuid
        import sys
        
        app_data_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ZR", "WeLearn学习助手")
        os.makedirs(app_data_path, exist_ok=True)
        settings_file = os.path.join(app_data_path, "settings.ini")
        
        settings = QSettings(settings_file, QSettings.IniFormat)
        
        # 生成或获取安装ID
        installation_id = settings.value("General/installation_id", "", type=str)
        if not installation_id:
            # 如果没有安装ID，生成一个新的
            installation_id = str(uuid.uuid4())
            settings.setValue("General/installation_id", installation_id)
            settings.sync()
            print(f"生成新的安装ID: {installation_id}")
        else:
            print(f"现有安装ID: {installation_id}")
        
        # 检查用户是否选择不再提醒
        dont_show = settings.value("General/dont_show_update_announcement", False, type=bool)
        announcement_shown = settings.value("General/announcement_shown", False, type=bool)
        last_version = settings.value("General/last_version", "", type=str)
        current_version = "V5.0.11"  # 更新当前版本号
        
        print(f"更新公告设置: 不再提醒={dont_show}")
        print(f"公告已显示={announcement_shown}")
        print(f"上次版本: {last_version}")
        print(f"当前版本: {current_version}")
        print(f"设置文件路径: {settings_file}")
        
        # 如果用户选择了不再显示且版本没有变化，则不显示公告
        if dont_show and announcement_shown and last_version == current_version:
            print("用户选择不再显示公告且版本未变化，跳过公告显示")
            return
        
        # 如果版本有更新，即使之前选择了不再显示，也要显示新版本的公告
        if dont_show and last_version != current_version:
            print(f"检测到版本更新({last_version} -> {current_version})，显示新版本公告")
            # 重置不再显示设置，让用户重新选择
            settings.setValue("General/dont_show_update_announcement", False)
            settings.setValue("General/last_version", current_version)
            settings.sync()
        
        print("开始显示更新公告")
        
        # 创建自定义对话框以支持滚动功能
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QCheckBox, QHBoxLayout, QStyle
        from PyQt5.QtCore import Qt, QSize
        from PyQt5.QtGui import QPixmap, QPalette
        
        dialog = QDialog(self)
        dialog.setWindowTitle("更新公告")
        dialog.setMinimumSize(600, 500)
        dialog.resize(600, 500)  # 设置初始大小
        # 移除问号帮助按钮
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 设置背景图片 - 使用更可靠的方法
        app_dir = self.get_app_directory()
        background_path = os.path.join(app_dir, 'ZR.png')
        print(f"获取到的背景图片路径: {background_path}")
        
        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建文本编辑区域用于显示公告
        announcement_text = QTextEdit()
        announcement_text.setReadOnly(True)
        announcement_text.setMinimumHeight(350)  # 设置最小高度
        
        announcement_content = f"WeLearn学习助手 {self.version}\n\n"

        
        # 最新更新公告
        announcement_content += "V5.0.11\n"
        announcement_content += "-修复了刷时长完成后显示的已完成数量不正确的问题\n"
        announcement_content += "-新增了正确率范围波动功能，允许设置正确率在指定范围内随机变化\n"
        announcement_content += "-优化了任务完成统计显示，现在正确显示已完成单元数量\n"
        announcement_content += "-更新了版本号到V5.0.11\n\n"
        
        announcement_content += "V5.0.9\n"
        announcement_content += "-修复了UnitsThread初始化参数错误\n"
        announcement_content += "-修复了UI背景图显示问题\n"
        announcement_content += "-更新了版本号到V5.0.9\n\n"
        
        announcement_content += "V5.0.7\n"
        announcement_content += "-修复了继续任务功能无法打开详情页的问题\n"
        announcement_content += "-优化了任务恢复流程，确保课程和单元数据加载完成后再恢复任务\n"
        announcement_content += "-修复了任务恢复时窗口不激活的问题\n"
        announcement_content += "-修复了变量初始化顺序问题，防止auto_login_attempted未定义错误\n"
        announcement_content += "-增强了窗口显示逻辑，确保对话框始终在前台显示\n"
        announcement_content += "-添加了详细的日志记录，便于调试和追踪问题\n"
        announcement_content += "-更新了版本号到V5.0.7\n\n"
        
        announcement_content += "V5.0.6\n"
        announcement_content += "-修复了继续任务功能无法打开详情页的问题\n"
        announcement_content += "-优化了任务恢复流程，确保课程和单元数据加载完成后再恢复任务\n"
        announcement_content += "-修复了任务恢复时窗口不激活的问题\n"
        announcement_content += "-更新了版本号到V5.0.6\n\n"
        
        announcement_content += "V5.0.5\n"
        announcement_content += "-修复了勾选任务选择继续进行后仍然没有继续任务的问题\n"
        announcement_content += "-优化了任务恢复时的线程启动逻辑\n"
        announcement_content += "-更新了版本号到V5.0.5\n\n"
        
        announcement_content += "V5.0.1\n"
        announcement_content += "-优化了任务恢复对话框，现在与主UI同时显示，提升用户体验\n"
        announcement_content += "-修复了任务恢复功能，确保未完成任务能够正确继续\n"
        announcement_content += "-改进了任务进度保存机制，提高了数据可靠性\n\n"
        
        announcement_content += "V4.6.6\n"
        announcement_content += "-修复了暂停选择彻底关闭依旧无响应的问题\n"
        announcement_content += "-由于继续任务功能bug无法修复，我迫不得已删除此功能\n\n"
        
        announcement_content += "V4.6.5\n"
        announcement_content += "-修复了点击\"Yes\"后没有自动打开账号详情管理页面的问题\n"
        announcement_content += "-修复了选择后台运行后弹出空白PowerShell弹窗的问题\n"
        announcement_content += "-修复了点击\"完全退出程序\"后程序仍在后台运行的问题\n"
        announcement_content += "-优化了任务恢复逻辑，确保未完成任务能够正确继续\n\n"
        
        announcement_content += "V4.6.4\n"
        announcement_content += "-修复了点击\"Yes\"后没有自动打开账号详情管理页面的问题\n"
        announcement_content += "-修复了选择后台运行后弹出空白PowerShell弹窗的问题\n"
        announcement_content += "-修复了点击\"完全退出程序\"后程序仍在后台运行的问题\n\n"
        
        announcement_content += "V4.6.2\n"
        announcement_content += "-修复了暂停任务后退出程序时的线程报错问题\n"
        announcement_content += "-优化了继续任务弹窗，使其与主UI一起出现并在屏幕中央\n"
        announcement_content += "-修复了点击继续任务后没有自动进行任务的问题\n\n"
        
        announcement_content += "V4.6.1\n"
        announcement_content += "-修复了弹窗中预计完成时间没有精确到秒的问题\n\n"
        
        announcement_content += "V4.6\n"
        announcement_content += "-修复了任务暂停后关闭程序时的线程报错问题\n"
        announcement_content += "-改进了任务停止逻辑，确保进度正确保存\n"
        announcement_content += "-优化了多单元并行刷时长的稳定性\n"
        announcement_content += "-修复了任务进度保存功能的潜在问题\n\n"
        
        announcement_content += "V4.5\n"
        announcement_content += "-实现了真正的多单元并行刷时长功能，充分利用设定的并发数\n"
        announcement_content += "-新增任务进度保存功能，支持中断后恢复未完成的任务\n"
        announcement_content += "-新增启动时检测未完成任务并提示继续的功能\n"
        announcement_content += "-优化了预计完成时间的计算，精确到秒\n\n"
        
        announcement_content += "V4.4\n"
        announcement_content += "-修复了打包后模块导入错误的问题，提高了程序稳定性\n"
        announcement_content += "-修复了workers.py中的缩进错误，确保后台任务正常运行\n"
        announcement_content += "-新增了任务开始前的弹窗提醒功能，显示选中单元数量\n"
        announcement_content += "-新增了刷时长任务开始前的预计完成时间提醒\n\n"
        
        announcement_content += "V4.3\n"
        announcement_content += "-修复了刷新按钮无效的问题，现在点击刷新按钮会重新从JSON文件加载数据\n"
        announcement_content += "-新增了程序工作日志输出到本地的功能，所有操作都会记录在logs目录下\n"
        announcement_content += "-优化了账号数据加载逻辑，提高了数据同步的可靠性\n"
        announcement_content += "-改进了错误处理机制，增加了详细的日志记录\n"
        announcement_content += "-修复了手动修改JSON文件后UI不更新的问题\n\n"
        
        announcement_content += "V4.2\n"
        announcement_content += "-修复了新版本无法读取旧版本账号数据的问题\n"
        announcement_content += "-修复了账号数据在UI界面不显示的问题\n"
        announcement_content += "-新增了刷新账号列表按钮，方便用户手动更新账户状态\n"
        announcement_content += "-优化了账号数据文件路径检测逻辑\n"
        announcement_content += "-改进了打包配置，避免账号数据被覆盖\n"
        announcement_content += "-增强了版本升级时的数据兼容性\n\n"
        announcement_content += "V4.1\n"
        announcement_content += "-实现了进入账号详情管理页面自动登录功能\n"
        announcement_content += "-优化了用户体验，减少了手动操作步骤\n"
        announcement_content += "-改进了登录流程，提高了使用便利性\n\n"
        
        announcement_content += "V4.0\n"
        announcement_content += "-修复了单元时长分配逻辑，确保每个单元的总时长都是用户输入的时长\n"
        announcement_content += "-优化了刷时长功能，现在每个单元独立处理，不再合并所有课程\n"
        announcement_content += "-改进了日志显示，更清晰地展示每个单元的处理进度\n"
        announcement_content += "-提高了多单元刷时长的准确性和稳定性\n\n"
        
        announcement_content += "V3.9\n"
        announcement_content += "-移除了所有弹窗中的无用问号按钮\n"
        announcement_content += "-优化了用户界面交互体验\n"
        announcement_content += "-改进了弹窗的视觉一致性\n\n"
        
        announcement_content += "V3.8\n"
        announcement_content += "-添加了任务完成后的提示音功能\n"
        announcement_content += "-修复了打包过程中Qt5Gui.dll提取失败的问题\n"
        announcement_content += "-优化了打包配置，提高了稳定性\n"
        announcement_content += "-改进了用户体验，增加了音频反馈\n\n"
        
        announcement_content += "V3.7\n"
        announcement_content += "-修复了公告弹窗背景显示问题\n"
        announcement_content += "-修复了用户未勾选不再显示但第二次打开不显示的问题\n"
        announcement_content += "-修复了公告弹窗没有居中的问题\n"
        announcement_content += "-优化了公告弹窗的布局和样式\n"
        announcement_content += "-改进了版本更新检测机制\n"
        announcement_content += "-增强了设置保存的可靠性\n\n"
        
        announcement_content += "V3.6\n"
        announcement_content += "-修复了公告弹窗背景显示问题\n"
        announcement_content += "-修复了用户未勾选不再显示但第二次打开不显示的问题\n"
        announcement_content += "-修复了公告弹窗没有居中的问题\n"
        announcement_content += "-优化了公告弹窗的布局和样式\n\n"
        
        announcement_content += "V3.5\n"
        announcement_content += "-修复了公告弹窗背景显示问题\n"
        announcement_content += "-修复了用户选择不再提示后公告仍然显示的问题\n"
        announcement_content += "-为公告添加了滚动功能，提高用户体验\n"
        announcement_content += "-优化了公告弹窗的布局和样式\n\n"
        
        announcement_content += "V3.4\n"
        announcement_content += "-修复了公告显示逻辑，现在每个新版本都会显示公告\n"
        announcement_content += "-移除了关闭程序弹窗的背景样式，使用系统默认样式\n"
        announcement_content += "-优化了公告弹窗的背景图片路径处理\n"
        announcement_content += "-改进了版本更新时的用户体验\n\n"
        
        announcement_content += "V3.3\n"
        announcement_content += "-修复了公告弹窗背景显示问题\n"
        announcement_content += "-优化了确定按钮的样式，使用绿色背景提高可见性\n"
        announcement_content += "-统一了弹窗的背景图片处理逻辑\n"
        announcement_content += "-改进了打包后的资源文件路径处理\n"
        announcement_content += "-修复了弹窗文字可读性问题\n\n"
        
        announcement_content += "V3.1\n"
        announcement_content += "-修改了 `main_window.py` 中的导入语句，添加了多种导入方式的尝试\n"
        announcement_content += "-在打包配置文件中添加了隐藏导入模块列表\n"
        announcement_content += "-修复了 `account_view.py` 中的语法错误（中文引号问题）\n"
        announcement_content += "-修改了 `ui/workers.py` 中的 `calculate_unit_time` 方法\n"
        announcement_content += "-修复前：每个小节都获得完整的用户输入时长（例如每个小节都获得3小时）\n"
        announcement_content += "-修复后：输入的单元时长平均分配给每个小节（例如3小时/6个小节=每个小节30分钟）\n"
        announcement_content += "-确保每个单元的总时长就是用户输入的时长，平均分配给每个小节\n\n"
        
        announcement_content += "V2.1\n"
        announcement_content += "-添加了Excel批量导入账号功能\n"
        announcement_content += "-输入框设置为半透明，以显示背景图片\n"
        announcement_content += "-修复了软件图标显示问题\n\n"
        
        announcement_content += "V1.1\n"
        announcement_content += "-添加单元时长单位自选\n"
        announcement_content += "-修复关闭程序导致后台运行\n"
        announcement_content += "-添加后台运行彻底关闭自选\n"
        announcement_content += "-默认单元时长与并行数调整为合适数值"
        announcement_content += "添加账号保存功能\n\n"
        
        announcement_text.setText(announcement_content)
        announcement_text.setFontPointSize(10)
        
        # 创建复选框
        checkbox = QCheckBox("不再提醒")
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_button = QPushButton("确定")
        ok_button.setDefault(True)
        ok_button.setMinimumWidth(80)  # 设置最小宽度
        button_layout.addWidget(ok_button)
        
        # 添加控件到主布局
        main_layout.addWidget(announcement_text)
        main_layout.addWidget(checkbox)
        main_layout.addLayout(button_layout)
        
        dialog.setLayout(main_layout)
        
        # 设置样式 - 使用更简单可靠的方法
        if background_path and os.path.exists(background_path):
            # 使用QPalette设置背景图片
            palette = dialog.palette()
            pixmap = QPixmap(background_path)
            if not pixmap.isNull():
                from PyQt5.QtGui import QBrush
                palette.setBrush(QPalette.Background, QBrush(pixmap))
                dialog.setPalette(palette)
                print("使用QPalette设置背景图片")
            else:
                print("无法加载背景图片，使用默认背景")
                dialog.setStyleSheet("QDialog { background-color: #f0f0f0; }")
        else:
            print("背景图片路径无效，使用默认背景")
            dialog.setStyleSheet("QDialog { background-color: #f0f0f0; }")
        
        # 设置文本编辑框样式
        announcement_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 220);
                padding: 10px;
                border-radius: 5px;
                border: 1px solid #ccc;
            }
        """)
        
        # 设置按钮样式
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 13px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        # 设置复选框样式
        checkbox.setStyleSheet("""
            QCheckBox {
                background-color: rgba(255, 255, 255, 220);
                font-size: 12px;
                padding: 5px;
            }
        """)
        
        # 居中显示对话框
        dialog.setGeometry(
            QStyle.alignedRect(
                Qt.LeftToRight,
                Qt.AlignCenter,
                dialog.size(),
                QApplication.desktop().availableGeometry()
            )
        )
        
        # 连接按钮点击事件
        ok_button.clicked.connect(dialog.accept)
        
        # 显示对话框
        dialog.exec_()
        
        # 处理用户选择
        if checkbox.isChecked():
            print("用户选择不再显示更新公告")
            settings.setValue("General/dont_show_update_announcement", True)
            # 标记公告已显示并更新版本号
            settings.setValue("General/announcement_shown", True)
            settings.setValue("General/last_version", current_version)
            settings.sync()
            
            # 验证设置是否保存成功
            dont_show_verify = settings.value("General/dont_show_update_announcement", False, type=bool)
            announcement_shown_verify = settings.value("General/announcement_shown", False, type=bool)
            print(f"验证设置保存: 不再提醒={dont_show_verify}, 公告已显示={announcement_shown_verify}")
            print(f"设置文件路径: {settings_file}")
            
            # 检查设置文件是否存在
            if os.path.exists(settings_file):
                print("设置文件存在")
                with open(settings_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"设置文件内容:\n{content}")
            else:
                print("警告: 设置文件不存在")
        else:
            print("用户未勾选不再提醒")
            # 即使用户未勾选"不再提醒"，也标记公告已显示并更新版本号
            settings.setValue("General/announcement_shown", True)
            settings.setValue("General/last_version", current_version)
            settings.sync()
            
            # 验证设置是否保存成功
            announcement_shown_verify = settings.value("General/announcement_shown", False, type=bool)
            print(f"验证设置保存: 公告已显示={announcement_shown_verify}")
            print(f"设置文件路径: {settings_file}")
            
            # 检查设置文件是否存在
            if os.path.exists(settings_file):
                print("设置文件存在")
            else:
                print("警告: 设置文件不存在")
    

    
    def closeEvent(self, event):
        """关闭窗口时的处理"""
        from core.logger import get_logger
        import threading
        import time
        import os
        
        try:
            import psutil
        except ImportError:
            psutil = None
        
        logger = get_logger("MainWindow")
        
        logger.info("主窗口关闭事件触发")
        logger.info(f"当前进程ID: {os.getpid()}")
        logger.info(f"当前线程ID: {threading.get_ident()}")
        logger.info(f"活动线程数: {threading.active_count()}")
        
        # 记录所有活动线程
        for thread in threading.enumerate():
            logger.info(f"活动线程: {thread.name} (ID: {thread.ident}, 是否运行中: {thread.is_alive()})")
        
        # 记录进程状态
        if psutil is not None:
            try:
                process = psutil.Process(os.getpid())
                logger.info(f"进程状态: {process.status()}")
                logger.info(f"进程内存使用: {process.memory_info().rss / 1024 / 1024:.2f} MB")
                logger.info(f"进程CPU使用率: {process.cpu_percent()}%")
                logger.info(f"进程线程数: {process.num_threads()}")
            except Exception as e:
                logger.error(f"获取进程状态失败: {str(e)}")
        else:
            logger.warning("psutil模块不可用，无法获取详细进程信息")
        
        msg_box = QMessageBox(QMessageBox.Question, "关闭程序", "您希望如何关闭程序？")
        # 移除问号帮助按钮
        msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        background_btn = msg_box.addButton("后台运行", QMessageBox.YesRole)
        close_btn = msg_box.addButton("完全关闭", QMessageBox.NoRole)
        cancel_btn = msg_box.addButton("取消", QMessageBox.RejectRole)
        msg_box.setDefaultButton(close_btn)
        
        # 获取主窗口的位置和大小
        main_window_geometry = self.frameGeometry()
        main_window_center = main_window_geometry.center()
        
        # 计算消息框的位置，使其在主窗口中央
        msg_box_size = msg_box.sizeHint()
        x = main_window_center.x() - msg_box_size.width() // 2
        y = main_window_center.y() - msg_box_size.height() // 2
        
        msg_box.move(x, y)
        
        reply = msg_box.exec_()
        
        if msg_box.clickedButton() == cancel_btn:
            logger.info("用户取消关闭程序")
            event.ignore()
            return
        elif msg_box.clickedButton() == background_btn:
            logger.info("用户选择后台运行")
            self.hide()
            
            # 隐藏所有打开的账号详情对话框
            for username, dialog in self.detail_dialogs.items():
                logger.info(f"隐藏账号详情对话框: {username}")
                dialog.hide()
            
            if self.tray_icon:
                # 显示更明显的通知，包含退出提示
                self.tray_icon.showMessage(
                    "WeLearn学习助手已最小化到系统托盘",
                    "程序仍在后台运行！\n右键点击托盘图标选择'退出程序'可完全关闭",
                    QSystemTrayIcon.Information,
                    5000  # 延长显示时间到5秒
                )
                
                # 同时在Windows通知区域显示气泡提示
                import subprocess
                try:
                    # 使用Windows通知命令，添加creationflags参数避免弹出窗口
                    import sys
                    if sys.platform == 'win32':
                        import subprocess
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = subprocess.SW_HIDE
                        
                        subprocess.run([
                            'powershell', '-Command',
                            'Add-Type -AssemblyName System.Windows.Forms; '
                            '$notify = New-Object System.Windows.Forms.NotifyIcon; '
                            '$notify.Icon = [System.Drawing.SystemIcons]::Information; '
                            '$notify.BalloonTipTitle = "WeLearn学习助手"; '
                            '$notify.BalloonTipText = "程序已最小化到系统托盘，右键托盘图标可退出"; '
                            '$notify.Visible = $true; '
                            '$notify.ShowBalloonTip(5000); '
                            'Start-Sleep -Seconds 6; '
                            '$notify.Dispose()'
                        ], check=True, capture_output=True, timeout=10, startupinfo=startupinfo)
                except Exception as e:
                    logger.warning(f"无法显示Windows通知: {str(e)}")
                
                # 启动定时提醒，每10分钟提醒一次用户程序仍在后台运行
                self.start_tray_reminder()
            event.ignore()
            return
        else:
            logger.info("用户选择完全关闭程序，开始清理资源")
            
            # 停止托盘提醒定时器
            self.stop_tray_reminder()
            
            # 记录关闭开始时间
            close_start_time = time.time()
            logger.info(f"开始关闭所有对话框，当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 关闭所有详情对话框
            logger.info(f"关闭 {len(self.detail_dialogs)} 个账号详情对话框")
            for username, dialog in list(self.detail_dialogs.items()):
                logger.debug(f"关闭账号详情对话框: {username}")
                dialog_start_time = time.time()
                try:
                    # 记录对话框线程状态
                    if hasattr(dialog, 'study_thread') and dialog.study_thread:
                        logger.info(f"对话框 {username} 任务线程状态: {dialog.study_thread.isRunning()}")
                        logger.info(f"对话框 {username} 任务线程是否已停止: {dialog.study_thread.isFinished()}")
                    
                    # 确保对话框中的线程被正确终止
                    if hasattr(dialog, 'closeEvent'):
                        logger.info(f"调用对话框 {username} 的closeEvent方法")
                        dialog.closeEvent(None)
                    dialog.close()
                    
                    # 如果对话框仍然存在，强制关闭
                    if not dialog.isHidden():
                        logger.warning(f"对话框 {username} 仍然可见，强制关闭")
                        dialog.hide()
                        
                        # 尝试终止对话框中的线程
                        if hasattr(dialog, 'study_thread') and dialog.study_thread:
                            if dialog.study_thread.isRunning():
                                logger.warning(f"强制终止对话框 {username} 中的线程")
                                dialog.study_thread.terminate()
                                dialog.study_thread.wait(500)
                                dialog.study_thread = None
                    
                    dialog_end_time = time.time()
                    logger.info(f"对话框 {username} 关闭完成，耗时: {dialog_end_time - dialog_start_time:.2f}秒")
                except Exception as e:
                    logger.error(f"关闭账号详情对话框时出错 {username}: {str(e)}")
            
            self.detail_dialogs.clear()
            
            # 隐藏托盘图标
            if self.tray_icon:
                logger.info("隐藏系统托盘图标")
                self.tray_icon.hide()
            
            # 记录关闭耗时
            close_end_time = time.time()
            logger.info(f"所有对话框关闭完成，总耗时: {close_end_time - close_start_time:.2f}秒")
            
            # 再次记录线程状态
            logger.info(f"关闭后活动线程数: {threading.active_count()}")
            for thread in threading.enumerate():
                logger.info(f"关闭后活动线程: {thread.name} (ID: {thread.ident}, 是否运行中: {thread.is_alive()})")
            
            # 再次记录进程状态
            try:
                process = psutil.Process(os.getpid())
                logger.info(f"关闭后进程状态: {process.status()}")
                logger.info(f"关闭后进程内存使用: {process.memory_info().rss / 1024 / 1024:.2f} MB")
                logger.info(f"关闭后进程CPU使用率: {process.cpu_percent()}%")
                logger.info(f"关闭后进程线程数: {process.num_threads()}")
            except Exception as e:
                logger.error(f"获取关闭后进程状态失败: {str(e)}")
            
            # 强制退出应用程序
            logger.info("调用QApplication.quit()退出应用程序")
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.quit()
            
            # 使用sys.exit()确保程序完全退出
            import sys
            import os
            
            # 在Windows上，可以使用更强制的方式退出
            if sys.platform == 'win32':
                try:
                    logger.info("在Windows平台上，使用os._exit(0)强制退出")
                    import os
                    # 使用Windows API强制结束当前进程
                    os._exit(0)
                except Exception as e:
                    logger.error(f"使用os._exit()时出错: {str(e)}")
            
            # 备用退出方式
            logger.info("使用sys.exit(0)退出")
            sys.exit(0)
            
            # 记录程序退出
            logger.info("WeLearn学习助手程序已完全退出")
            
            event.accept()
    
    def init_tray(self):
        """初始化系统托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("系统不支持托盘功能")
            return
        
        self.tray_icon = self.create_tray_icon()
        
        tray_menu = QMenu()
        
        show_action = tray_menu.addAction("显示主窗口")
        show_action.triggered.connect(self.show_from_tray)
        
        tray_menu.addSeparator()
        
        # 添加一个更明显的退出选项
        quit_action = tray_menu.addAction("完全退出程序")
        quit_action.triggered.connect(self.quit_from_tray)
        # 设置退出选项的字体，使其更明显
        font = quit_action.font()
        font.setBold(True)
        quit_action.setFont(font)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # 设置托盘图标的悬停提示
        self.tray_icon.setToolTip("WeLearn学习助手 - 右键退出程序")
        
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        
        self.tray_icon.show()
    
    def create_tray_icon(self):
        """创建托盘图标"""
        # 使用统一的路径获取方法
        app_dir = self.get_app_directory()
        icon_path = os.path.join(app_dir, 'ZR.ico')
        
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            print(f"已设置托盘图标: {icon_path}")
        else:
            print(f"托盘图标文件不存在: {icon_path}")
            # 使用系统默认图标
            icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        
        return QSystemTrayIcon(icon, self)
    
    def show_from_tray(self):
        """从托盘恢复显示主窗口"""
        self.show()
        self.raise_()
        self.activateWindow()
        
        # 停止托盘提醒
        self.stop_tray_reminder()
    
    def _ensure_dialog_active(self, dialog):
        """确保对话框处于活动状态并显示在前台"""
        try:
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            dialog.setWindowState(dialog.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        except Exception as e:
            from core.logger import get_logger
            logger = get_logger("MainWindow")
            logger.error(f"激活对话框时出错: {str(e)}")
    
    def start_tray_reminder(self):
        """启动托盘提醒定时器"""
        from PyQt5.QtCore import QTimer
        from core.logger import get_logger
        logger = get_logger("MainWindow")
        
        # 停止之前的定时器（如果有）
        self.stop_tray_reminder()
        
        # 创建新的定时器，每10分钟提醒一次
        self.tray_reminder_timer = QTimer()
        self.tray_reminder_timer.timeout.connect(self.show_tray_reminder)
        self.tray_reminder_timer.start(600000)  # 10分钟 = 600000毫秒
        
        logger.info("已启动托盘提醒定时器，每10分钟提醒一次")
    
    def stop_tray_reminder(self):
        """停止托盘提醒定时器"""
        from core.logger import get_logger
        logger = get_logger("MainWindow")
        
        if self.tray_reminder_timer and self.tray_reminder_timer.isActive():
            self.tray_reminder_timer.stop()
            self.tray_reminder_timer = None
            logger.info("已停止托盘提醒定时器")
    
    def show_tray_reminder(self):
        """显示托盘提醒"""
        from core.logger import get_logger
        logger = get_logger("MainWindow")
        
        if self.tray_icon and not self.isVisible():
            logger.info("显示托盘提醒通知")
            self.tray_icon.showMessage(
                "WeLearn学习助手仍在后台运行",
                "双击托盘图标显示主窗口，或右键选择'完全退出程序'",
                QSystemTrayIcon.Information,
                8000  # 显示8秒
            )
    
    def quit_from_tray(self):
        """从托盘完全退出程序"""
        from core.logger import get_logger
        import threading
        import time
        import psutil
        import os
        
        logger = get_logger("MainWindow")
        
        logger.info("从系统托盘退出程序")
        logger.info(f"当前进程ID: {os.getpid()}")
        logger.info(f"当前线程ID: {threading.get_ident()}")
        logger.info(f"活动线程数: {threading.active_count()}")
        
        # 记录所有活动线程
        for thread in threading.enumerate():
            logger.info(f"活动线程: {thread.name} (ID: {thread.ident}, 是否运行中: {thread.is_alive()})")
        
        # 记录进程状态
        try:
            process = psutil.Process(os.getpid())
            logger.info(f"进程状态: {process.status()}")
            logger.info(f"进程内存使用: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            logger.info(f"进程CPU使用率: {process.cpu_percent()}%")
            logger.info(f"进程线程数: {process.num_threads()}")
        except Exception as e:
            logger.error(f"获取进程状态失败: {str(e)}")
        
        # 停止托盘提醒定时器
        self.stop_tray_reminder()
        
        # 记录关闭开始时间
        close_start_time = time.time()
        logger.info(f"开始从托盘关闭所有对话框，当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 关闭所有详情对话框
        logger.info(f"关闭 {len(self.detail_dialogs)} 个账号详情对话框")
        for username, dialog in list(self.detail_dialogs.items()):
            logger.debug(f"关闭账号详情对话框: {username}")
            dialog_start_time = time.time()
            try:
                # 记录对话框线程状态
                if hasattr(dialog, 'study_thread') and dialog.study_thread:
                    logger.info(f"对话框 {username} 任务线程状态: {dialog.study_thread.isRunning()}")
                    logger.info(f"对话框 {username} 任务线程是否已停止: {dialog.study_thread.isFinished()}")
                
                # 确保对话框中的线程被正确终止
                if hasattr(dialog, 'closeEvent'):
                    logger.info(f"调用对话框 {username} 的closeEvent方法")
                    dialog.closeEvent(None)
                dialog.close()
                
                # 如果对话框仍然存在，强制关闭
                if not dialog.isHidden():
                    logger.warning(f"对话框 {username} 仍然可见，强制关闭")
                    dialog.hide()
                    
                    # 尝试终止对话框中的线程
                    if hasattr(dialog, 'study_thread') and dialog.study_thread:
                        if dialog.study_thread.isRunning():
                            logger.warning(f"强制终止对话框 {username} 中的线程")
                            dialog.study_thread.terminate()
                            dialog.study_thread.wait(500)
                            dialog.study_thread = None
                
                dialog_end_time = time.time()
                logger.info(f"对话框 {username} 关闭完成，耗时: {dialog_end_time - dialog_start_time:.2f}秒")
            except Exception as e:
                logger.error(f"关闭账号详情对话框时出错 {username}: {str(e)}")
        
        self.detail_dialogs.clear()
        
        # 隐藏托盘图标
        if self.tray_icon:
            logger.info("隐藏系统托盘图标")
            self.tray_icon.hide()
        
        # 记录关闭耗时
        close_end_time = time.time()
        logger.info(f"所有对话框关闭完成，总耗时: {close_end_time - close_start_time:.2f}秒")
        
        # 再次记录线程状态
        logger.info(f"关闭后活动线程数: {threading.active_count()}")
        for thread in threading.enumerate():
            logger.info(f"关闭后活动线程: {thread.name} (ID: {thread.ident}, 是否运行中: {thread.is_alive()})")
        
        # 再次记录进程状态
        try:
            process = psutil.Process(os.getpid())
            logger.info(f"关闭后进程状态: {process.status()}")
            logger.info(f"关闭后进程内存使用: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            logger.info(f"关闭后进程CPU使用率: {process.cpu_percent()}%")
            logger.info(f"关闭后进程线程数: {process.num_threads()}")
        except Exception as e:
            logger.error(f"获取关闭后进程状态失败: {str(e)}")
        
        # 强制退出应用程序
        logger.info("调用QApplication.quit()退出应用程序")
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.quit()
        
        # 使用sys.exit()确保程序完全退出
        import sys
        import os
        
        # 在Windows上，可以使用更强制的方式退出
        if sys.platform == 'win32':
            try:
                logger.info("在Windows平台上，使用os._exit(0)强制退出")
                import os
                # 使用Windows API强制结束当前进程
                os._exit(0)
            except Exception as e:
                logger.error(f"使用os._exit()时出错: {str(e)}")
        
        # 备用退出方式
        logger.info("使用sys.exit(0)退出")
        sys.exit(0)
        
        # 记录程序退出
        logger.info("WeLearn学习助手程序已从托盘完全退出")
    
    def on_tray_icon_activated(self, reason):
        """托盘图标激活事件"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show_from_tray()
    
    def resizeEvent(self, event):
        """窗口大小改变时重新设置背景图片"""
        super().resizeEvent(event)
        
        # 使用统一的路径获取方法
        app_dir = self.get_app_directory()
        bg_path = os.path.join(app_dir, 'ZR.png')
        if bg_path and os.path.exists(bg_path):
            palette = self.palette()
            pixmap = QPixmap(bg_path)
            palette.setBrush(self.backgroundRole(), QBrush(pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)))
            self.setPalette(palette)
